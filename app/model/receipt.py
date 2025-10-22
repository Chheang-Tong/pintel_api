# app/model/receipt.py
from datetime import datetime
from ..extensions import db

class Receipt(db.Model):
    __tablename__ = "receipts"
    id = db.Column(db.Integer, primary_key=True)
    cart_uuid = db.Column(db.String(36), index=True)
    snapshot_json = db.Column(db.JSON)  # the full cart totals + lines at checkout time
    total = db.Column(db.Numeric(12,2))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
