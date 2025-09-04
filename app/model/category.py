# --- models/category.py ---
from ..extensions import db

# ---------------- CATEGORY ----------------
class Category(db.Model):
    __tablename__ = "category"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    products = db.relationship(
        "Product", 
        backref="category", 
        lazy=True
        )

    def as_dict(self):
        return {
            "id": self.id, 
            "name": self.name
            }