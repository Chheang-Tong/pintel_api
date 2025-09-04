from datetime import datetime
from ..extensions import db
from ..model import Cart, CartItem, Coupon, CartCoupon, Product, Category
from ..utils.money import D, round_money, Money

def _csv_to_intset(s: str):
    if not s: return set()
    return {int(x) for x in s.split(",") if x.strip().isdigit()}

def _apply_item_discount(unit_price: Money, discount_type: str|None, discount_value: Money) -> Money:
    if not discount_type or D(discount_value) <= 0:
        return D(0)
    if discount_type == "percent":
        return round_money(unit_price * D(discount_value) / D(100))
    if discount_type == "fixed":
        return round_money(min(unit_price, D(discount_value)))
    return D(0)

def _product_category_map(items):
    pids = {it.product_id for it in items}
    if not pids:
        return {}
    rows = db.session.query(Product.id, Product.category_id).filter(Product.id.in_(pids)).all()
    return {pid: cat_id for pid, cat_id in rows}

def _eligible_item(item: CartItem, coupon: Coupon, prod_cat_map) -> bool:
    ex_prod = _csv_to_intset(coupon.exclude_product_ids or "")
    if item.product_id in ex_prod:
        return False
    inc_cat = _csv_to_intset(coupon.include_category_ids or "")
    if not inc_cat:
        return True
    return prod_cat_map.get(item.product_id) in inc_cat

def _apply_coupon_to_items(items, coupon: Coupon):
    """
    Returns (item_discount_delta, per_item_discounts_map)
    """
    total = D(0)
    per_item = {}
    if coupon.kind == "free_shipping" or coupon.target == "invoice":
        return total, per_item

    prod_cat_map = _product_category_map(items)

    for it in items:
        if not _eligible_item(it, coupon, prod_cat_map):
            continue
        unit = D(it.unit_price)
        per_unit_disc = D(0)
        if coupon.kind == "percent":
            per_unit_disc = round_money(unit * coupon.value / D(100))
        elif coupon.kind == "fixed":
            per_unit_disc = round_money(min(unit, coupon.value))
        line_disc = per_unit_disc * it.qty
        per_item[it.id] = line_disc
        total += line_disc
    return total, per_item

def _apply_invoice_coupon(subtotal_after_item_discounts: Money, coupon: Coupon, shipping_total: Money):
    if coupon.kind == "free_shipping":
        return D(0), shipping_total
    if coupon.kind == "percent":
        return round_money(subtotal_after_item_discounts * coupon.value / D(100)), None
    if coupon.kind == "fixed":
        return round_money(min(subtotal_after_item_discounts, coupon.value)), None
    return D(0), None

def recalc_cart(cart: Cart):
    """
    Recalculate totals from items + coupons.
    Order:
      1) item-level explicit discounts (CartItem)
      2) item-level coupons (target=item)
      3) invoice-level coupons (target=invoice, free_shipping)
      4) shipping
      5) tax (optional; disabled by default)
    """
    # 1) item level
    sub_total = D(0)
    item_discount_total = D(0)

    for it in cart.items:
        unit = D(it.unit_price)
        qty = it.qty
        line_sub = unit * qty
        it.line_subtotal = round_money(line_sub)

        per_unit_disc = _apply_item_discount(unit, it.discount_type, D(it.discount_value))
        line_disc = per_unit_disc * qty
        it.line_discount = round_money(line_disc)
        it.line_total = round_money(line_sub - line_disc)

        sub_total += it.line_subtotal
        item_discount_total += it.line_discount

    # 2) item-level coupons
    coupon_item_total = D(0)
    now = datetime.utcnow()
    for cc in cart.coupons:
        c = cc.coupon
        if not c.active: 
            continue
        if c.starts_at and now < c.starts_at: 
            continue
        if c.ends_at and now > c.ends_at: 
            continue
        # gate using freshly computed pre-discount subtotal
        if sub_total < D(c.min_subtotal or 0):
            continue
        add_total, _ = _apply_coupon_to_items(cart.items, c)
        coupon_item_total += add_total

    # 3) invoice-level coupons
    subtotal_after_items = sub_total - item_discount_total - coupon_item_total
    subtotal_after_items = max(D(0), subtotal_after_items)

    invoice_discount_total = D(0)
    shipping_total = D(cart.shipping_total or 0)  # keep previously set shipping unless changed by coupon
    free_shipping_applied = False

    for cc in cart.coupons:
        c = cc.coupon
        if not c.active: 
            continue
        if c.starts_at and now < c.starts_at: 
            continue
        if c.ends_at and now > c.ends_at: 
            continue
        if sub_total < D(c.min_subtotal or 0):
            continue

        if c.kind == "free_shipping":
            shipping_total = D(0)
            free_shipping_applied = True
            continue

        if c.target == "invoice":
            disc, _ = _apply_invoice_coupon(subtotal_after_items, c, shipping_total)
            invoice_discount_total += disc
            subtotal_after_items = max(D(0), subtotal_after_items - disc)

    # 4) shipping restore if no free shipping
    if not free_shipping_applied:
        shipping_total = D(cart.shipping_total or 0)

    # 5) tax (disabled — set to True to enable simple 10%)
    tax_total = D(0)
    grand_total = round_money(subtotal_after_items + shipping_total + tax_total)

    # persist/caches
    cart.sub_total = round_money(sub_total)
    cart.item_discount_total = round_money(item_discount_total + coupon_item_total)
    cart.invoice_discount_total = round_money(invoice_discount_total)
    cart.shipping_total = round_money(shipping_total)
    cart.tax_total = round_money(tax_total)
    cart.grand_total = round_money(grand_total)

    db.session.flush()

# helpers to sanitize item discount input
ALLOWED_ITEM_DISCOUNT = {None, "percent", "fixed"}

def sanitize_item_discount(discount_type, discount_value):
    from ..utils.money import D
    dt = (discount_type or None)
    if dt not in ALLOWED_ITEM_DISCOUNT:
        dt = None
    dv = D(discount_value or 0)
    if dv < 0:
        dv = D(0)
    if dt == "percent" and dv > 100:
        dv = D(100)
    return dt, dv
