# app/model/cart.py
from __future__ import annotations
import uuid as _uuid
from decimal import Decimal
from sqlalchemy.sql import func
from ..extensions import db

class Cart(db.Model):
    __tablename__ = "cart"

    id = db.Column(db.Integer, primary_key=True)
    # NEW: a stable public identifier for the cart
    uuid = db.Column(db.String(36), unique=True, index=True, default=lambda: str(_uuid.uuid4()))

    # (Optional) keep session_id if you still want to support old clients
    user_id = db.Column(db.Integer, nullable=True, index=True)
    session_id = db.Column(db.String(64), nullable=True, index=True)
    status = db.Column(db.String(16), default="active", index=True)  # active, checked_out, abandoned
    created_at = db.Column(db.DateTime, server_default=func.now())
    updated_at = db.Column(db.DateTime, onupdate=func.now(), server_default=func.now())

    items = db.relationship(
        "CartItem",
        backref="cart",
        cascade="all, delete-orphan",
        lazy="joined",
        order_by="CartItem.id.asc()"
    )

    def subtotal_dec(self) -> Decimal:
        return sum((i.line_total_dec() for i in self.items), Decimal("0.00"))

    def total_dec(self) -> Decimal:
        return self.subtotal_dec()

    def as_api(self):
        return {
            "id": self.id,
            "uuid": self.uuid,                     # expose uuid to client
            "status": self.status,
            "items": [i.as_api() for i in self.items],
            "subtotal": str(self.subtotal_dec()),
            "total": str(self.total_dec()),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class CartItem(db.Model):
    __tablename__ = "cart_item"

    id = db.Column(db.Integer, primary_key=True)
    cart_id = db.Column(db.Integer, db.ForeignKey("cart.id"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False, index=True)

    # snapshot fields (copy at time of add; you can keep them in sync or leave as snapshot)
    product_name = db.Column(db.String(255), nullable=False)
    product_price = db.Column(db.Float, nullable=False, default=0.0)
    quantity = db.Column(db.Integer, nullable=False, default=1)

    created_at = db.Column(db.DateTime, server_default=func.now())
    updated_at = db.Column(db.DateTime, onupdate=func.now(), server_default=func.now())

    product = db.relationship("Product", lazy="joined")

    def line_total_dec(self) -> Decimal:
        return Decimal(str(self.product_price)) * Decimal(self.quantity)

    def as_api(self):
        # choose main image url if available
        main_img = None
        if self.product and self.product.images:
            for img in self.product.images:
                if img.main:
                    main_img = img.image_url or img.image_path
                    break
            if not main_img:
                main_img = (self.product.images[0].image_url
                            or self.product.images[0].image_path)

        return {
            "id": self.id,
            "product_id": self.product_id,
            "name": self.product_name,
            "price": self.product_price,
            "quantity": self.quantity,
            "line_total": float(self.quantity) * float(self.product_price),
            "image_url": main_img,
            "product": {
                "id": self.product.id if self.product else self.product_id,
                "slug": self.product.slug if self.product else None,
                "unit": self.product.unit if self.product else None,
                "ean_code": self.product.ean_code if self.product else None,
            },
        }
