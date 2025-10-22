from ..model import Order, OrderItem, Product

def _gen_order_code():
    # simple code generator; replace with sequence if you like
    from datetime import datetime
    return "ORD-" + datetime.utcnow().strftime("%Y%m%d-%H%M%S%f")[:18]

@bp.post("/checkout")
def checkout():
    cart = _resolve_cart()
    if not cart.items:
        return err("cart is empty", 422)

    payload = request.get_json(silent=True) or {}
    customer = payload.get("customer") or {}
    shipping_address = payload.get("shipping_address") or {}
    payment_req = payload.get("payment") or {"method": "cod"}

    if not customer.get("name") or not customer.get("phone"):
        return err("customer name and phone are required", 422)

    try:
        # Lock product rows to avoid oversell
        ids = [i.product_id for i in cart.items]
        products = (
            db.session.query(Product)
            .filter(Product.id.in_(ids))
            .with_for_update()
            .all()
        )
        pmap = {p.id: p for p in products}

        # Recompute & validate
        subtotal_before = 0.0
        items_discount_total = 0.0
        snapshot_items = []

        for it in cart.items:
            p = pmap.get(it.product_id)
            if not p or p.status is False:
                return err(f"product {it.product_id} unavailable", 409)

            # keep qty; ensure still valid
            qty = _normalized_qty(p, it.quantity, current_qty=0)
            if qty < 1 or qty != it.quantity:
                return err(f"requested qty for {p.name} not available", 409)

            unit_price = float(p.price or it.product_price or 0.0)
            it.product_price = unit_price  # ensure discount computed off current price

            unit_discount = _unit_discount_amount(it)  # uses your caps
            unit_final = round(unit_price - unit_discount, 2)

            line_before = round(unit_price * qty, 2)
            line_total  = round(unit_final * qty, 2)

            subtotal_before += line_before
            items_discount_total += round(line_before - line_total, 2)

            snapshot_items.append({
                "product_id": it.product_id,
                "name": p.name,
                "image_url": getattr(it, "image_url", None),
                "unit_price": unit_price,
                "discount_type": it.discount_type,
                "discount_value": it.discount_value,
                "unit_discount": unit_discount,
                "unit_final_price": unit_final,
                "quantity": qty,
                "line_total": line_total,
            })

        # Cart-level discount & coupons
        subtotal_after_items = _cart_subtotal_after_item_and_cart_discounts(cart)

        coupon_total = 0.0
        if cart.coupons:
            for link in cart.coupons:
                c = link.coupon
                ok_apply, reason = _can_apply_coupon(cart, c)
                if not ok_apply:
                    return err(f"coupon '{c.code}' invalid: {reason}", 422)
                coupon_total += _coupon_discount_amount(c, subtotal_after_items - coupon_total)

        total = round(max(0.0, subtotal_after_items - coupon_total), 2)

        # Create order + items
        order = Order(
            code=_gen_order_code(),
            status="pending",
            customer_name=customer.get("name"),
            phone=customer.get("phone"),
            email=customer.get("email"),
            address_json=shipping_address,
            subtotal=round(subtotal_before, 2),
            items_discount_total=round(items_discount_total, 2),
            cart_discount_amount=round(subtotal_before - subtotal_after_items - items_discount_total, 2),
            coupon_total=round(coupon_total, 2),
            total=total,
            cart_uuid=cart.uuid,
        )
        db.session.add(order)
        db.session.flush()

        for s in snapshot_items:
            db.session.add(OrderItem(order_id=order.id, **s))

        # Decrement stock for tracked products
        for it in cart.items:
            p = pmap[it.product_id]
            if (p.subtract_stock or "yes") == "yes":
                if int(p.quantity or 0) < it.quantity:
                    return err(f"{p.name} just sold out", 409)
                p.quantity = int(p.quantity or 0) - int(it.quantity or 0)

        # Payment handling (stub)
        if (payment_req.get("method") or "cod").lower() != "cod":
            # TODO: integrate gateway here
            pass

        # Close cart
        cart.status = "checked_out"
        cart.items.clear()
        cart.coupons.clear()

        db.session.commit()

        resp = ok("order created", {"order": order.as_api()}, status=201)
        resp.headers["X-Order-Id"] = str(order.id)
        return resp

    except Exception as e:
        db.session.rollback()
        return err(f"checkout failed: {e}", 500)
