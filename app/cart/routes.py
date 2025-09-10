# app/cart/routes.py
from __future__ import annotations
from flask import request, jsonify

from app.utils.api import api_ok, api_error
from ..extensions import db
from . import bp
from datetime import datetime, timezone
from ..model import Product, Coupon, CartCoupon, Cart, CartItem 

# # ---- standard API response format ------------------------------------------
def ok(msg, data=None, status=200):
    r = jsonify(api_ok(msg, data)); r.status_code = status; return r
def err(msg, status=400, data=None):
    r = jsonify(api_error(msg, data)); r.status_code = status; return r

# ---- helpers ---------------------------------------------------------------

_COUPON_DTYPES = {"percent", "fixed"}

def _now_utc():
    return datetime.now(timezone.utc)

def _validate_coupon_structure(c: "Coupon"):
    if (c.ctype or "").lower() not in _COUPON_DTYPES:
        raise ValueError("coupon type must be 'percent' or 'fixed'")
    if c.value is None or float(c.value) <= 0:
        raise ValueError("coupon value must be > 0")
    if c.ctype == "percent" and float(c.value) > 100:
        raise ValueError("percent coupon must be ≤ 100")

def _coupon_is_active(c: "Coupon") -> bool:
    if not c.active:
        return False
    now = _now_utc()
    if c.starts_at and now < c.starts_at:
        return False
    if c.ends_at and now > c.ends_at:
        return False
    return True

def _cart_subtotal_after_item_and_cart_discounts(cart: Cart) -> float:
    # You already compute per-item net in _unit_net_price. Sum it:
    subtotal = 0.0
    for it in cart.items:
        subtotal += _unit_net_price(it) * int(it.quantity or 0)
    # If you store cart-level discount fields:
    if getattr(cart, "cart_discount_type", None):
        t = (cart.cart_discount_type or "").lower()
        v = float(cart.cart_discount_value or 0.0)
        if t == "percent":
            subtotal -= max(0.0, min(subtotal, subtotal * (v/100.0)))
        elif t == "fixed":
            subtotal -= max(0.0, min(subtotal, v))
    return round(max(0.0, subtotal), 2)

def _coupon_discount_amount(c: "Coupon", base_amount: float) -> float:
    if base_amount <= 0:
        return 0.0
    if (c.ctype or "").lower() == "percent":
        return round(min(base_amount, base_amount * (float(c.value)/100.0)), 2)
    # fixed currency
    return round(min(base_amount, float(c.value)), 2)

def _can_apply_coupon(cart: Cart, c: "Coupon") -> tuple[bool, str | None]:
    _validate_coupon_structure(c)
    if not _coupon_is_active(c):
        return False, "invalid or inactive coupon"

    base = _cart_subtotal_after_item_and_cart_discounts(cart)

    if c.min_subtotal and base < float(c.min_subtotal):
        return False, f"subtotal must be ≥ {float(c.min_subtotal):.2f}"

    # prevent duplicate in this cart (you already check by code on add)
    used_in_cart = sum(1 for link in cart.coupons if link.coupon_id == c.id)
    if c.max_uses_per_cart and used_in_cart >= c.max_uses_per_cart:
        return False, "coupon already applied maximum times for this cart"

    # global cap (requires you to increment usage when orders complete — not shown here)
    if c.max_uses is not None and c.max_uses < 0:
        return False, "coupon exhausted"

    # stackability: if false, only allow when no other coupons
    if (c.stackable is False) and len(cart.coupons) > 0:
        return False, "coupon cannot be combined"

    # no numeric error; amount 0 still means “applies but gives 0”
    return True, None
# ============================================================================



_VALID_DTYPES = {"percent", "fixed"}

def _sanitize_discount(dtype: str | None, dval) -> tuple[str | None, float | None]:
    if not dtype:
        return None, None
    dtype = str(dtype).lower().strip()
    try:
        dval = float(dval)
    except Exception:
        dval = None
    if dtype not in {"percent", "fixed"}:
        raise ValueError("discount type must be 'percent' or 'fixed'")
    if dval is None or dval <= 0:
        raise ValueError("discount value must be > 0")

    if dtype == "percent":
        # NEW: cap percent at 50, not 100
        # dval = _cap_percent(dval)
        dval=_validate_percent(dval)
        if dval <= 0:
            raise ValueError(f"percent discount must be > 0 and ≤ {MAX_PERCENT_DISCOUNT}")
    return dtype, dval

def _clear_discount(item: CartItem):
    item.discount_type = None
    item.discount_value = None


def register_error_handlers(app):
    @app.errorhandler(ValueError)
    def handle_value_error(e):
        r = jsonify({"ok": False, "message": str(e), "data": None})
        r.status_code = 422
        return r


# ---- discount caps ----------------------------------------------------------
MAX_FIXED_DISCOUNT_RATE = 0.50 
MAX_PERCENT_DISCOUNT     = 50.0

# def _cap_fixed_to_unit_price(item: CartItem, dval: float) -> float:
#     """Cap per-unit fixed discount to ≤ 50% of unit price, clamp [0, cap], round to cents."""
#     unit_price = float(item.product_price or 0.0)
#     cap = unit_price * MAX_FIXED_DISCOUNT_RATE
#     try:
#         d = float(dval)
#     except Exception:
#         d = 0.0
#     d = max(0.0, min(d, cap))
#     return round(d, 2)

# def _cap_percent(dval: float) -> float:
#     """Cap percent discount to ≤ 50%."""
#     try:
#         d = float(dval)
#     except Exception:
#         d = 0.0
#     d = max(0.0, min(d, MAX_PERCENT_DISCOUNT))
#     return round(d, 2)


def _validate_percent(dval: float) -> float:
    try:
        d = float(dval)
    except Exception:
        raise ValueError("invalid percent discount")
    if d <= 0 or d > MAX_PERCENT_DISCOUNT:
        raise ValueError(f"percent discount must be > 0 and ≤ {MAX_PERCENT_DISCOUNT}")
    return round(d, 2)

def _validate_fixed(item: CartItem, dval: float) -> float:
    try:
        d = float(dval)
    except Exception:
        raise ValueError("invalid fixed discount")
    unit_price = float(item.product_price or 0.0)
    cap = unit_price * MAX_FIXED_DISCOUNT_RATE
    if d <= 0 or d > cap:
        raise ValueError(f"fixed discount must be > 0 and ≤ {cap:.2f}")
    return round(d, 2)

#   --------------------------------------------------------------------------

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

# ============================================================================
def _unit_discount_amount(item: CartItem) -> float:
    price = float(item.product_price or 0.0)
    dtype = (item.discount_type or "").lower()
    dval  = float(item.discount_value or 0.0)

    if dtype == "percent":
        amt = price * (dval / 100.0)
    elif dtype == "fixed":
        amt = dval                   # already capped when set
    else:
        amt = 0.0

    # never discount below 0 or above price
    amt = max(0.0, min(amt, price))
    return round(amt, 2)

def _unit_net_price(item: CartItem) -> float:
    return round(float(item.product_price or 0.0) - _unit_discount_amount(item), 2)

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

@bp.patch("/items/<int:item_id>/discount")
def set_item_discount(item_id: int):
    cart = _resolve_cart()
    item: CartItem | None = next((i for i in cart.items if i.id == item_id), None)
    if not item:
        return err("item not found in this cart", 404)

    data = request.get_json(silent=True) or {}
    if data.get("clear") is True:
        _clear_discount(item)
    else:
        if "type" not in data or "value" not in data:
            return err("type and value are required (or set clear=true)", 422)
        try:
            dtype, dval = _sanitize_discount(data.get("type"), data.get("value"))
            if dtype == "percent":
                dval = _validate_percent(dval)           # may raise ValueError
            elif dtype == "fixed":
                dval = _validate_fixed(item, dval)       # may raise ValueError
        except ValueError as e:
            return err(str(e), 422)

        item.discount_type = dtype
        item.discount_value = dval

    db.session.commit()
    resp = ok("discount updated", cart.as_api(), status=200)
    resp.headers["X-Cart-Id"] = cart.uuid
    return resp

@bp.patch("/items/by-product/<int:product_id>/discount")
def set_item_discount_by_product(product_id: int):
    cart = _resolve_cart()
    item = _find_item_by_product(cart, product_id)
    if not item:
        return err("item not found in this cart", 404)

    data = request.get_json(silent=True) or {}
    if data.get("clear") is True:
        _clear_discount(item)
    else:
        if "type" not in data or "value" not in data:
            return err("type and value are required (or set clear=true)", 422)
        try:
            dtype, dval = _sanitize_discount(data.get("type"), data.get("value"))
            if dtype == "percent":
                dval = _validate_percent(dval)           # may raise ValueError
            elif dtype == "fixed":
                dval = _validate_fixed(item, dval)       # may raise ValueError
        except ValueError as e:
            return err(str(e), 422)

        item.discount_type = dtype
        item.discount_value = dval

    db.session.commit()
    resp = ok("discount updated", cart.as_api(), status=200)
    resp.headers["X-Cart-Id"] = cart.uuid
    return resp


@bp.patch("/discount")
def set_cart_discount():
    """
    Body (apply): { "type": "percent" | "fixed", "value": number }
    Body (clear): { "clear": true }
    Applies at cart/invoice level AFTER item discounts, BEFORE coupons.
    """
    cart = _resolve_cart()
    data = request.get_json(silent=True) or {}

    if data.get("clear") is True:
        cart.cart_discount_type = None
        cart.cart_discount_value = None
    else:
        if "type" not in data or "value" not in data:
            return err("type and value are required (or set clear=true)", 422)
        try:
            dtype, dval = _sanitize_discount(data.get("type"), data.get("value"))
        except ValueError as e:
            return err(str(e), 422)
        cart.cart_discount_type = dtype
        cart.cart_discount_value = dval

    db.session.commit()
    resp = ok("cart discount updated", cart.as_api(), status=200)
    resp.headers["X-Cart-Id"] = cart.uuid
    return resp

@bp.post("/coupons")
def add_coupon():
    """
    Body: { "code": "SUMMER10" }
    Validates existence & active==True.
    Prevents duplicates.
    """
    cart = _resolve_cart()
    data = request.get_json(silent=True) or {}
    code = (data.get("code") or "").strip()
    if not code:
        return err("code is required", 422)

    coupon = Coupon.query.filter(Coupon.code.ilike(code)).first()
    if not coupon or not getattr(coupon, "active", True):
        return err("invalid or inactive coupon", 404)

    # prevent duplicate link
    if any(link.coupon_id == coupon.id for link in cart.coupons):
        return err("coupon already applied", 409)

    db.session.add(CartCoupon(cart_id=cart.id, coupon_id=coupon.id))
    db.session.commit()

    resp = ok("coupon added", cart.as_api(), status=200)
    resp.headers["X-Cart-Id"] = cart.uuid
    return resp


@bp.get("/coupons")
def list_coupons():
    cart = _resolve_cart()
    resp = ok("coupons", cart.as_api(), status=200)
    resp.headers["X-Cart-Id"] = cart.uuid
    return resp


@bp.delete("/coupons/<code>")
def remove_coupon(code: str):
    cart = _resolve_cart()
    # find by code among this cart's links
    link = None
    for l in cart.coupons:
        c = getattr(l, "coupon", None)
        if c and c.code.lower() == code.lower():
            link = l
            break
    if not link:
        return err("coupon not found on this cart", 404)

    db.session.delete(link)
    db.session.commit()

    resp = ok("coupon removed", cart.as_api(), status=200)
    resp.headers["X-Cart-Id"] = cart.uuid
    return resp


@bp.delete("/coupons")
def clear_coupons():
    cart = _resolve_cart()
    cart.coupons.clear()
    db.session.commit()
    resp = ok("all coupons removed", cart.as_api(), status=200)
    resp.headers["X-Cart-Id"] = cart.uuid
    return resp
