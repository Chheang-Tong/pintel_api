from datetime import datetime
from ..extensions import db

class Order(db.Model):
    __tablename__ = "orders"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(32), unique=True, index=True)  # e.g., "ORD-20251022-0001"
    status = db.Column(db.String(20), default="pending", index=True)

    # Customer snapshot
    customer_name = db.Column(db.String(120))
    phone = db.Column(db.String(50))
    email = db.Column(db.String(120))
    address_json = db.Column(db.JSON)  # if your DB lacks JSON, switch to Text and dump as str

    # Money snapshot
    subtotal = db.Column(db.Numeric(12, 2))
    items_discount_total = db.Column(db.Numeric(12, 2))
    cart_discount_amount = db.Column(db.Numeric(12, 2))
    coupon_total = db.Column(db.Numeric(12, 2))
    total = db.Column(db.Numeric(12, 2))

    # Link back for audit/debug (not a FK constraint)
    cart_uuid = db.Column(db.String(36), index=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    items = db.relationship(
        "OrderItem",
        backref="order",
        cascade="all, delete-orphan",
        lazy="joined"
    )

    def as_api(self):
        return {
            "id": self.id,
            "code": self.code,
            "status": self.status,
            "customer": {
                "name": self.customer_name,
                "phone": self.phone,
                "email": self.email,
                "address": self.address_json,
            },
            "money": {
                "subtotal": float(self.subtotal or 0),
                "items_discount_total": float(self.items_discount_total or 0),
                "cart_discount_amount": float(self.cart_discount_amount or 0),
                "coupon_total": float(self.coupon_total or 0),
                "total": float(self.total or 0),
            },
            "items": [i.as_api() for i in self.items],
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "cart_uuid": self.cart_uuid,
        }

class OrderItem(db.Model):
    __tablename__ = "order_items"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False, index=True)

    product_id = db.Column(db.Integer, index=True)
    name = db.Column(db.String(255))
    image_url = db.Column(db.String(255))

    unit_price = db.Column(db.Numeric(12, 2))
    discount_type = db.Column(db.String(10))
    discount_value = db.Column(db.Numeric(12, 2))
    unit_discount = db.Column(db.Numeric(12, 2))
    unit_final_price = db.Column(db.Numeric(12, 2))

    quantity = db.Column(db.Integer, nullable=False)
    line_total = db.Column(db.Numeric(12, 2))

    def as_api(self):
        return {
            "product_id": self.product_id,
            "name": self.name,
            "image_url": self.image_url,
            "unit_price": float(self.unit_price or 0),
            "discount": {
                "type": self.discount_type,
                "value": float(self.discount_value or 0) if self.discount_value is not None else None,
                "unit_discount": float(self.unit_discount or 0),
            },
            "unit_final_price": float(self.unit_final_price or 0),
            "quantity": self.quantity,
            "line_total": float(self.line_total or 0),
        }
