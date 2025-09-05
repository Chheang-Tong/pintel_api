# --- app/model/coupon.py ---

from ..extensions import db
from sqlalchemy.sql import func

class Coupon(db.Model):
    __tablename__ = "coupon"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(64), unique=True, nullable=False, index=True)

    # "percent" or "fixed"
    ctype = db.Column(db.String(16), nullable=False, default="percent")
    value = db.Column(db.Float, nullable=False, default=0.0)

    active = db.Column(db.Boolean, default=True, index=True)

    # Optional constraints
    min_subtotal = db.Column(db.Float, nullable=True)      # require cart subtotal >= this
    max_uses = db.Column(db.Integer, nullable=True)        # global usage cap
    starts_at = db.Column(db.DateTime, nullable=True)
    ends_at = db.Column(db.DateTime, nullable=True)

    # Per-cart safety
    max_uses_per_cart = db.Column(db.Integer, nullable=True, default=1)
    stackable = db.Column(db.Boolean, default=True)        # can combine with other coupons?

    created_at = db.Column(db.DateTime, server_default=func.now())
    updated_at = db.Column(db.DateTime, onupdate=func.now(), server_default=func.now())

    # relationship hook (optional)
    links = db.relationship("CartCoupon", back_populates="coupon", lazy="selectin")

class CartCoupon(db.Model):
    __tablename__ = "cart_coupon"
    id = db.Column(db.Integer, primary_key=True)
    cart_id = db.Column(db.Integer, db.ForeignKey("cart.id", ondelete="CASCADE"), index=True, nullable=False)
    coupon_id = db.Column(db.Integer, db.ForeignKey("coupon.id", ondelete="CASCADE"), index=True, nullable=False)
    cart = db.relationship("Cart", back_populates="coupons")
    coupon = db.relationship("Coupon", back_populates="links")
