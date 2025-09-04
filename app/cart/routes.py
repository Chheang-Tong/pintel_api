# app/cart/routes.py
from __future__ import annotations
from flask import request, jsonify
from ..extensions import db
from ..model import Product
from ..model.cart import Cart, CartItem
from . import bp

def api_ok(msg, data=None): return {"ok": True, "message": msg, "data": data}
def api_error(msg, data=None): return {"ok": False, "message": msg, "data": data}
def ok(msg, data=None, status=200):
    r = jsonify(api_ok(msg, data)); r.status_code = status; return r
def err(msg, status=400, data=None):
    r = jsonify(api_error(msg, data)); r.status_code = status; return r

# ---- helpers ---------------------------------------------------------------
# near your other helpers
_VALID_DTYPES = {"percent", "fixed"}

def _sanitize_discount(dtype: str | None, dval) -> tuple[str | None, float | None]:
    if not dtype:
        return None, None
    dtype = str(dtype).lower().strip()
    try:
        dval = float(dval)
    except Exception:
        dval = None
    if dtype not in _VALID_DTYPES:
        raise ValueError("discount type must be 'percent' or 'fixed'")
    if dval is None or dval <= 0:
        raise ValueError("discount value must be > 0")
    if dtype == "percent" and dval > 100:
        dval = 100.0
    return dtype, dval

def _get_or_create_cart_by_uuid(cart_uuid: str | None) -> Cart:
    q = Cart.query.filter_by(status="active")
    if cart_uuid:
        q = q.filter(Cart.uuid == cart_uuid)
    cart = q.first()
    if not cart:
        cart = Cart(status="active")           # uuid autogenerates in model
        db.session.add(cart)
        db.session.commit()
    return cart

# Optional: keep old clients working (maps X-Session-Id -> cart)
def _get_or_create_cart_by_legacy_session() -> Cart:
    sid = request.headers.get("X-Session-Id")  # legacy header
    if not sid:
        return None
    q = Cart.query.filter_by(status="active", session_id=sid)
    cart = q.first()
    if not cart:
        cart = Cart(status="active", session_id=sid)
        db.session.add(cart)
        db.session.commit()
    return cart

def _resolve_cart() -> Cart:
    cart_uuid = request.headers.get("X-Cart-Id")
    if cart_uuid:
        return _get_or_create_cart_by_uuid(cart_uuid)
    legacy = _get_or_create_cart_by_legacy_session()
    if legacy:
        return legacy
    return _get_or_create_cart_by_uuid(None)

# ---- endpoints -------------------------------------------------------------

@bp.get("")
def get_cart():
    cart = _resolve_cart()
    resp = ok("cart", cart.as_api(), status=200)
    resp.headers["X-Cart-Id"] = cart.uuid            # <- return UUID to client
    return resp

@bp.post("")
def create_or_get_cart():
    cart = _resolve_cart()
    resp = ok("cart ready", cart.as_api(), status=201)
    resp.headers["X-Cart-Id"] = cart.uuid
    return resp

@bp.post("/items")
def add_item():
    """
    Body: { "product_id": int, "quantity" | "qty": int }
    Header: X-Cart-Id: <uuid>   (preferred)
    """
    cart = _resolve_cart()
    data = request.get_json(silent=True) or {}
    product_id = data.get("product_id")
    qty = int(data.get("quantity") or data.get("qty") or 1)

    if not product_id:
        return err("product_id is required", 422)
    if qty < 1:
        return err("quantity must be >= 1", 422)

    product: Product | None = db.session.get(Product, product_id)
    if not product or (product.status is False):
        return err("product not found or inactive", 404)

    min_order = product.minimum_order or 1
    if qty < min_order:
        qty = min_order

    # Stock validation only (no immediate subtraction)
    if (product.subtract_stock or "yes") == "yes":
        available = int(product.quantity or 0)
        if available <= 0:
            return err("out of stock", 409)
        if qty > available:
            qty = available

    # Upsert item
    item = next((i for i in cart.items if i.product_id == product.id), None)
    if item:
        new_qty = item.quantity + qty
        if (product.subtract_stock or "yes") == "yes":
            max_allowed = int(product.quantity or 0) + item.quantity
            if new_qty > max_allowed:
                new_qty = max_allowed
        if new_qty < min_order:
            new_qty = min_order
        item.quantity = new_qty
    else:
        item = CartItem(
            cart_id=cart.id,
            product_id=product.id,
            product_name=product.name,
            product_price=product.price,
            quantity=qty,
        )
        db.session.add(item)

    db.session.commit()

    resp = ok("item added", cart.as_api(), status=201)
    resp.headers["X-Cart-Id"] = cart.uuid
    return resp
# ==============================================
# ---- qty helpers -----------------------------------------------------------

def _stock_enabled(product) -> bool:
    # treat None/"" as "yes"
    return (product.subtract_stock or "yes") == "yes"

def _normalized_qty(product, requested_qty: int, *, current_qty: int = 0) -> int:
    """
    Enforce min order and available stock.
    current_qty: the quantity already in cart (for this item), so stock cap is (product.quantity + current_qty)
    """
    if requested_qty < 0:
        requested_qty = 0

    min_order = int(product.minimum_order or 1)
    if 0 < requested_qty < min_order:
        requested_qty = min_order

    if _stock_enabled(product):
        available_now = int(product.quantity or 0) + int(current_qty or 0)
        if requested_qty > available_now:
            requested_qty = available_now

    return requested_qty

def _find_item_by_product(cart: Cart, product_id: int) -> CartItem | None:
    return next((i for i in cart.items if i.product_id == product_id), None)

# ---- update by cart-item id ------------------------------------------------
@bp.put("/items/<int:item_id>")
@bp.patch("/items/<int:item_id>")
def update_item(item_id: int):
    """
    Body: { "quantity": int }
    Rules:
      - quantity must be >= 1
      - enforce product.minimum_order
      - enforce stock limits
    """
    cart = _resolve_cart()
    item: CartItem | None = next((i for i in cart.items if i.id == item_id), None)
    if not item:
        return err("item not found in this cart", 404)

    data = request.get_json(silent=True) or {}
    if "quantity" not in data:
        return err("quantity is required", 422)

    qty = int(data.get("quantity") or 0)
    if qty <= 0:
        return err("quantity must be >= 1", 422)

    product = item.product
    # normalize against min_order and stock
    qty = _normalized_qty(product, qty, current_qty=item.quantity)

    if qty < (product.minimum_order or 1):
        return err(f"minimum order is {product.minimum_order}", 422)

    item.quantity = qty
    db.session.commit()

    resp = ok("item updated", cart.as_api(), status=200)
    resp.headers["X-Cart-Id"] = cart.uuid
    return resp

# ---- update by product_id (alternative) ------------------------------------
@bp.put("/items/by-product/<int:product_id>")
@bp.patch("/items/by-product/<int:product_id>")
def update_item_by_product(product_id: int):
    """
    Body: { "quantity": int }
    Rules:
      - quantity must be >= 1 (reject otherwise)
      - enforce product.minimum_order (reject if below)
      - enforce stock limits (cap to available)
      - create the item if it doesn't exist yet
    """
    cart = _resolve_cart()
    data = request.get_json(silent=True) or {}

    if "quantity" not in data:
        return err("quantity is required", 422)

    # Validate base quantity input
    req_qty = int(data.get("quantity") or 0)
    if req_qty <= 0:
        return err("quantity must be >= 1", 422)

    # Fetch product
    product: Product | None = db.session.get(Product, product_id)
    if not product or (product.status is False):
        return err("product not found or inactive", 404)

    # Enforce minimum order explicitly (reject if below)
    min_order = int(product.minimum_order or 1)
    if req_qty < min_order:
        return err(f"minimum order is {min_order}", 422)

    # Find existing item (if any)
    item = _find_item_by_product(cart, product_id)
    current_qty = int(item.quantity) if item else 0

    # Normalize against stock (caps at available + current in cart)
    qty = _normalized_qty(product, req_qty, current_qty=current_qty)

    # Save
    if item:
        item.quantity = qty
    else:
        db.session.add(CartItem(
            cart_id=cart.id,
            product_id=product.id,
            product_name=product.name,
            product_price=product.price,
            quantity=qty,
        ))

    db.session.commit()
    resp = ok("item updated", cart.as_api(), status=200)
    resp.headers["X-Cart-Id"] = cart.uuid
    return resp
# ==============================================================================
# ---- remove a single item by cart-item id ----------------------------------
@bp.delete("/items/<int:item_id>")
def remove_item(item_id: int):
    cart = _resolve_cart()
    item: CartItem | None = next((i for i in cart.items if i.id == item_id), None)
    if not item:
        return err("item not found in this cart", 404)

    db.session.delete(item)
    db.session.commit()

    resp = ok("item removed", cart.as_api(), status=200)
    resp.headers["X-Cart-Id"] = cart.uuid
    return resp


# ---- remove a single item by product_id ------------------------------------
@bp.delete("/items/by-product/<int:product_id>")
def remove_item_by_product(product_id: int):
    cart = _resolve_cart()
    item = next((i for i in cart.items if i.product_id == product_id), None)
    if not item:
        return err("item not found in this cart", 404)

    db.session.delete(item)
    db.session.commit()

    resp = ok("item removed", cart.as_api(), status=200)
    resp.headers["X-Cart-Id"] = cart.uuid
    return resp


# ---- clear all items (empty the cart, keep same cart uuid) -----------------
@bp.delete("/items")
def clear_cart_items():
    cart = _resolve_cart()
    # because of cascade="all, delete-orphan", clearing the list deletes rows
    cart.items.clear()
    db.session.commit()

    resp = ok("all items removed", cart.as_api(), status=200)
    resp.headers["X-Cart-Id"] = cart.uuid
    return resp


# ---- remove the cart itself (soft-delete + hand back a fresh cart) ---------
@bp.delete("")
def remove_cart():
    """
    Marks the current cart as 'abandoned' (soft delete) and returns a fresh empty cart.
    This avoids clients holding an X-Cart-Id that points to a non-active cart.
    """
    cart = _resolve_cart()
    cart.status = "abandoned"
    db.session.commit()

    # hand back a new active cart
    new_cart = _get_or_create_cart_by_uuid(None)

    resp = ok("cart removed; new cart ready", new_cart.as_api(), status=200)
    resp.headers["X-Cart-Id"] = new_cart.uuid
    return resp
