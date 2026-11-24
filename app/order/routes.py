# app/order/routes.py
from flask import Blueprint, request
from ..extensions import db
from ..model import Order
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
      - status=pending|paid|fulfilled|cancelled
      - phone=078...
      - email=...
      - code=ORD-...
      - start=YYYY-MM-DD
      - end=YYYY-MM-DD (inclusive)
    """
    q = Order.query

    status = request.args.get("status")
    phone  = request.args.get("phone")
    email  = request.args.get("email")
    code   = request.args.get("code")
    start  = request.args.get("start")
    end    = request.args.get("end")

    if status: q = q.filter(Order.status == status)
    if phone:  q = q.filter(Order.phone == phone)
    if email:  q = q.filter(Order.email == email)
    if code:   q = q.filter(Order.code == code)

    from datetime import datetime, timedelta
    if start:
        q = q.filter(Order.created_at >= datetime.fromisoformat(start))
    if end:
        # make end inclusive for the whole day
        q = q.filter(Order.created_at < datetime.fromisoformat(end) + timedelta(days=1))

    page = int(request.args.get("page", 1))
    per  = min(int(request.args.get("per_page", 20)), 100)

    q = q.order_by(Order.created_at.desc())
    paged = q.paginate(page=page, per_page=per, error_out=False)

    return ok("orders", {
        "page": page,
        "per_page": per,
        "total": paged.total,
        "items": [o.as_api() for o in paged.items],
    })

@bp.get("/<int:order_id>")
def get_order(order_id: int):
    o = Order.query.get(order_id)
    if not o: return err("order not found", 404)
    return ok("order", o.as_api())

@bp.get("/by-phone/<phone>")
def orders_by_phone(phone):
    q = (Order.query.filter(Order.phone == phone)
                  .order_by(Order.created_at.desc())
                  .limit(50))
    return ok("orders", [o.as_api() for o in q.all()])

