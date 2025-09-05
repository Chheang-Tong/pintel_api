# app/model/cart.py
from __future__ import annotations
import uuid as _uuid
from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy.sql import func
from ..extensions import db
from .coupon import CartCoupon 

MONEY = Decimal("0.01")

def _money(x: Decimal) -> Decimal:
    return x.quantize(MONEY, rounding=ROUND_HALF_UP)

class Cart(db.Model):
    __tablename__ = "cart"

    id = db.Column(db.Integer, primary_key=True)
    uuid = db.Column(db.String(36), unique=True, index=True, default=lambda: str(_uuid.uuid4()))
    user_id = db.Column(db.Integer, nullable=True, index=True)
    session_id = db.Column(db.String(64), nullable=True, index=True)
    status = db.Column(db.String(16), default="active", index=True)
    created_at = db.Column(db.DateTime, server_default=func.now())
    updated_at = db.Column(db.DateTime, onupdate=func.now(), server_default=func.now())

    # NEW: cart/invoice level manual discount
    cart_discount_type = db.Column(db.String(16), nullable=True)   # "percent" | "fixed" | None
    cart_discount_value = db.Column(db.Float, nullable=True)

    items = db.relationship(
        "CartItem",
        backref="cart",
        cascade="all, delete-orphan",
        lazy="joined",
        order_by="CartItem.id.asc()"
    )

    # NEW: applied coupons on this cart (through table CartCoupon)
    coupons = db.relationship(
        "CartCoupon",
        back_populates="cart",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    # --------- money helpers / totals ----------
    def subtotal_before_dec(self) -> Decimal:
        # sum of unit_price * qty (no discounts)
        return _money(sum((i.unit_price_dec() * Decimal(i.quantity) for i in self.items), Decimal("0")))

    def items_discount_total_dec(self) -> Decimal:
        # sum of per-unit discount * qty
        return _money(sum((i.unit_discount_dec() * Decimal(i.quantity) for i in self.items), Decimal("0")))

    def subtotal_dec(self) -> Decimal:
        # after item discounts
        return _money(sum((i.line_total_dec() for i in self.items), Decimal("0")))

    def cart_manual_discount_dec(self, base: Decimal | None = None) -> Decimal:
        base = self.subtotal_dec() if base is None else base
        dtype = (self.cart_discount_type or "").lower().strip() if self.cart_discount_type else None
        dval = Decimal(str(self.cart_discount_value or 0))
        if not dtype or dval <= 0:
            return Decimal("0")
        if dtype == "percent":
            if dval > 100:
                dval = Decimal("100")
            return _money(base * dval / Decimal("100"))
        if dtype == "fixed":
            return _money(min(dval, base))
        return Decimal("0")

    def coupons_total_dec(self, base_after_cart_discount: Decimal | None = None) -> tuple[Decimal, list[dict]]:
        """
        Apply coupons sequentially on the remaining base (after cart manual discount).
        Each coupon uses its type/value, capped so totals never go below zero.
        Returns (total_coupon_amount, breakdown_list).
        """
        remaining = self.subtotal_dec() if base_after_cart_discount is None else base_after_cart_discount
        applied_total = Decimal("0")
        breakdown = []

        # Expect each CartCoupon has .coupon eager joined
        for link in self.coupons:
            c = getattr(link, "coupon", None)
            if not c or not getattr(c, "active", True):
                continue
            ctype = (c.ctype or "").lower().strip()
            cval = Decimal(str(c.value or 0))
            if cval <= 0:
                continue

            if ctype == "percent":
                if cval > 100:
                    cval = Decimal("100")
                amount = _money(remaining * cval / Decimal("100"))
            elif ctype == "fixed":
                amount = _money(min(cval, remaining))
            else:
                continue

            # cap so we don't go negative
            if amount > remaining:
                amount = remaining
            remaining = _money(remaining - amount)
            applied_total += amount

            breakdown.append({
                "code": getattr(c, "code", None),
                "type": ctype,
                "value": float(cval),
                "applied": float(amount),
            })

            if remaining <= 0:
                break

        return _money(applied_total), breakdown

    def total_dec(self) -> Decimal:
        base = self.subtotal_dec()
        cart_disc = self.cart_manual_discount_dec(base)
        base_after_cart = _money(base - cart_disc)
        coupon_total, _ = self.coupons_total_dec(base_after_cart)
        total = _money(base_after_cart - coupon_total)
        if total < 0:
            total = Decimal("0")
        return total

    def as_api(self):
        base_before = self.subtotal_before_dec()
        items_disc = self.items_discount_total_dec()
        base_after_items = self.subtotal_dec()
        cart_disc = self.cart_manual_discount_dec(base_after_items)
        base_after_cart = _money(base_after_items - cart_disc)
        coupon_total, coupon_list = self.coupons_total_dec(base_after_cart)
        grand = _money(base_after_cart - coupon_total)
        if grand < 0:
            grand = Decimal("0")

        return {
            "id": self.id,
            "uuid": self.uuid,
            "status": self.status,
            "items": [i.as_api() for i in self.items],
            "totals": {
                "subtotal_before": float(base_before),          # no discounts
                "items_discount_total": float(items_disc),      # sum of per-item discounts
                "subtotal": float(base_after_items),            # after item discounts
                "cart_discount": {
                    "type": self.cart_discount_type,
                    "value": self.cart_discount_value,
                    "amount": float(cart_disc),
                },
                "coupon_total": float(coupon_total),
                "total": float(grand),
            },
            "coupons": coupon_list,  # [{code, type, value, applied}]
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class CartItem(db.Model):
    __tablename__ = "cart_item"

    id = db.Column(db.Integer, primary_key=True)
    cart_id = db.Column(db.Integer, db.ForeignKey("cart.id"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False, index=True)

    product_name = db.Column(db.String(255), nullable=False)
    product_price = db.Column(db.Float, nullable=False, default=0.0)
    quantity = db.Column(db.Integer, nullable=False, default=1)

    # NEW: per-item discount
    discount_type = db.Column(db.String(16), nullable=True)   # "percent" | "fixed" | None
    discount_value = db.Column(db.Float, nullable=True)

    created_at = db.Column(db.DateTime, server_default=func.now())
    updated_at = db.Column(db.DateTime, onupdate=func.now(), server_default=func.now())

    product = db.relationship("Product", lazy="joined")

    # ---- price helpers ----
    def unit_price_dec(self) -> Decimal:
        return Decimal(str(self.product_price))

    def unit_discount_dec(self) -> Decimal:
        price = self.unit_price_dec()
        dtype = (self.discount_type or "").lower().strip() if self.discount_type else None
        dval = Decimal(str(self.discount_value or 0))
        if not dtype or dval <= 0:
            return Decimal("0")
        if dtype == "percent":
            if dval > 100:
                dval = Decimal("100")
            return _money(price * dval / Decimal("100"))
        if dtype == "fixed":
            return _money(min(dval, price))
        return Decimal("0")

    def unit_final_price_dec(self) -> Decimal:
        final_ = self.unit_price_dec() - self.unit_discount_dec()
        if final_ < 0:
            final_ = Decimal("0")
        return _money(final_)

    def line_total_before_dec(self) -> Decimal:
        return _money(self.unit_price_dec() * Decimal(self.quantity))

    def line_total_dec(self) -> Decimal:
        return _money(self.unit_final_price_dec() * Decimal(self.quantity))

    def as_api(self):
        main_img = None
        if self.product and getattr(self.product, "images", None):
            for img in self.product.images:
                if getattr(img, "main", False):
                    main_img = img.image_url or img.image_path
                    break
            if not main_img and self.product.images:
                main_img = (self.product.images[0].image_url
                            or self.product.images[0].image_path)

        return {
            "id": self.id,
            "product_id": self.product_id,
            "name": self.product_name,
            "price": float(self.unit_price_dec()),
            "quantity": self.quantity,
            "discount": {
                "type": self.discount_type,
                "value": self.discount_value,
                "unit_discount": float(self.unit_discount_dec()),
            },
            "line_total_before": float(self.line_total_before_dec()),
            "line_total": float(self.line_total_dec()),
            "unit_final_price": float(self.unit_final_price_dec()),
            "image_url": main_img,
            "product": {
                "id": self.product.id if self.product else self.product_id,
                "slug": getattr(self.product, "slug", None) if self.product else None,
                "unit": getattr(self.product, "unit", None) if self.product else None,
                "ean_code": getattr(self.product, "ean_code", None) if self.product else None,
            },
        }
