# app/receipt/routes.py

from flask import Blueprint, request
from ..extensions import db
from ..model import Receipt
from app.utils.api import api_ok, api_error
from . import bp

def ok(msg, data=None, status=200):
    from flask import jsonify; r = jsonify(api_ok(msg, data)); r.status_code = status; return r
def err(msg, status=400, data=None):
    from flask import jsonify; r = jsonify(api_error(msg, data)); r.status_code = status; return r

@bp.get("")
def list():
    """
    Query params:
      - page, per_page
      - cart_uuid=...
      - start, end (YYYY-MM-DD)
    """
    q = Receipt.query
    cart_uuid = request.args.get("cart_uuid")
    start     = request.args.get("start")
    end       = request.args.get("end")

    if cart_uuid: q = q.filter(Receipt.cart_uuid == cart_uuid)

    from datetime import datetime, timedelta
    if start:
        q = q.filter(Receipt.created_at >= datetime.fromisoformat(start))
    if end:
        q = q.filter(Receipt.created_at < datetime.fromisoformat(end) + timedelta(days=1))

    page = int(request.args.get("page", 1))
    per  = min(int(request.args.get("per_page", 20)), 100)

    q = q.order_by(Receipt.created_at.desc())
    paged = q.paginate(page=page, per_page=per, error_out=False)

    return ok("receipts", {
        "page": page, "per_page": per, "total": paged.total,
        "items": [{
            "id": r.id,
            "cart_uuid": r.cart_uuid,
            "total": float(r.total or 0),
            "created_at": r.created_at.isoformat(),
        } for r in paged.items],
    })

@bp.get("/<int:rid>")
def get_receipt(rid: int):
    r = Receipt.query.get(rid)
    if not r: return err("receipt not found", 404)
    # snapshot_json contains the full cart at checkout time (items, totals)
    return ok("receipt", {
        "id": r.id,
        "cart_uuid": r.cart_uuid,
        "total": float(r.total or 0),
        "created_at": r.created_at.isoformat(),
        "snapshot": r.snapshot_json,
    })
