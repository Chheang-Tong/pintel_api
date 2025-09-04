# app/model/product.py
from ..extensions import db
from sqlalchemy.sql import func

class Product(db.Model):
    __tablename__ = "product"
    id = db.Column(db.Integer, primary_key=True)
    barcode = db.Column(db.String(180), nullable=False, unique=True)
    slug = db.Column(db.String(255), index=True)
    name = db.Column(db.String(255), nullable=False, index=True)
    code = db.Column(db.String(64), unique=True, index=True)

    price = db.Column(db.Float, nullable=False, default=0.0)
    is_pin = db.Column(db.Boolean, default=False)
    price_format = db.Column(db.String(64))          # e.g. "$2.50" or "៛10,000"

    quantity = db.Column(db.Integer, default=0)
    minimum_order = db.Column(db.Integer, default=1)
    subtract_stock = db.Column(db.String(16), default="yes")      # "yes"/"no"
    out_of_stock_status = db.Column(db.String(32), default="in_stock")
    date_available = db.Column(db.String(32))        # keep string if you want to echo exactly

    sort_order = db.Column(db.Integer, default=0)
    status = db.Column(db.Boolean, default=True)
    is_new = db.Column(db.Boolean, default=False)
    viewed = db.Column(db.Integer, default=0)
    is_favourite = db.Column(db.Boolean, default=False)
    reviewable = db.Column(db.Boolean, default=True)

    unit = db.Column(db.String(32))                  # e.g. "cup", "pcs"
    ean_code = db.Column(db.String(64))

    created_at = db.Column(db.DateTime, server_default=func.now())
    updated_at = db.Column(db.DateTime, onupdate=func.now(), server_default=func.now())

    images = db.relationship(
        "ProductImage",
        backref="product",
        cascade="all, delete-orphan",
        lazy="joined",
        order_by="ProductImage.id.asc()",
    )
    category_id = db.Column(
        db.Integer,
        db.ForeignKey("category.id"),
        nullable=True
    )

    def as_api(self):
        return {
            "id": self.id,
            "barcode": self.barcode,
            "slug": self.slug,
            "name": self.name,
            "code": self.code,
            "price": self.price,
            "is_pin": self.is_pin,
            "price_format": self.price_format,
            "quantity": self.quantity,
            "minimum_order": self.minimum_order,
            "subtract_stock": self.subtract_stock,
            "out_of_stock_status": self.out_of_stock_status,
            "date_available": self.date_available,
            "sort_order": self.sort_order,
            "status": self.status,
            "is_new": self.is_new,
            "viewed": self.viewed,
            "is_favourite": self.is_favourite,
            "reviewable": self.reviewable,
            "images": [img.as_api() for img in self.images],
            "promotion": None,                        # fill if you have a promo table
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "unit": self.unit,
            "ean_code": self.ean_code,
            "category": self.category.as_dict() if self.category else None,
        }

class ProductImage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False, index=True)
    name = db.Column(db.String(255))
    image_path = db.Column(db.String(512))           # relative path on disk
    main = db.Column(db.Boolean, default=False)

    # If you already store full URL, keep it here; otherwise build it in as_api()
    image_url = db.Column(db.String(1024))

    def as_api(self):
        return {
            "id": self.id,
            "name": self.name,
            "image_path": self.image_path,
            "main": self.main,
            "image_url": self.image_url,
        }
