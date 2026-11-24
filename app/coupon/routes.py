# app/coupon/routes.py
from __future__ import annotations
from flask import Blueprint, request, jsonify
from sqlalchemy import func
from ..extensions import db
from ..utils.api import api_ok, api_error
from ..model import Coupon
from datetime import datetime, timezone
from . import bp

def _parse_iso8601(s: str | None):
    if not s:
        return None
    s = s.strip()
    # support trailing 'Z' (UTC)
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
        # make sure we always store aware UTC if tz provided, else naive (your choice)
        if dt.tzinfo:
            return dt.astimezone(timezone.utc).replace(tzinfo=None)  # store naive UTC
        return dt
    except Exception:
        return None  # let validation catch it below
    
@bp.post("")
def create_coupon():
    data = request.get_json(silent=True) or {}
    code = (data.get("code") or "").strip()
    ctype = (data.get("ctype") or "percent").lower().strip()
    value = float(data.get("value") or 0)
    active = bool(data.get("active", True))
    min_subtotal = data.get("min_subtotal")
    max_uses = data.get("max_uses")
    max_uses_per_cart = data.get("max_uses_per_cart", 1)
    stackable = bool(data.get("stackable", True))
    starts_at = data.get("starts_at")  # ISO8601 or None
    ends_at = data.get("ends_at")

    if not code:
        return jsonify(api_error("code is required")), 400
    if ctype not in ("percent", "fixed"):
        return jsonify(api_error("ctype must be 'percent' or 'fixed'")), 400
    if value <= 0:
        return jsonify(api_error("value must be > 0")), 400

    # unique case-insensitive
    existing = Coupon.query.filter(func.lower(Coupon.code) == code.lower()).first()
    if existing:
        return jsonify(api_error("Coupon code already exists")), 400

    c = Coupon(
        code=code,
        ctype=ctype,
        value=value,
        active=active,
        min_subtotal=min_subtotal,
        max_uses=max_uses,
        max_uses_per_cart=max_uses_per_cart,
        stackable=stackable,
    )

    starts_at = _parse_iso8601(data.get("starts_at"))
    ends_at   = _parse_iso8601(data.get("ends_at"))

    if data.get("starts_at") and not starts_at:
        return jsonify(api_error("Invalid datetime format for starts_at")), 400
    if data.get("ends_at") and not ends_at:
        return jsonify(api_error("Invalid datetime format for ends_at")), 400

    c.starts_at = starts_at
    c.ends_at = ends_at


    db.session.add(c)
    db.session.commit()
    return jsonify(api_ok("Coupon created", {
        "id": c.id,
        "code": c.code,
        "ctype": c.ctype,
        "value": c.value,
        "active": c.active,
    })), 201

@bp.get("")
def list_coupons():
    q = Coupon.query
    active = request.args.get("active")
    if active is not None:
        q = q.filter(Coupon.active == (active.lower() == "true"))

    items = q.order_by(Coupon.id.desc()).all()
    payload = [
        {
            "id": c.id,
            "code": c.code,
            "ctype": c.ctype,
            "value": c.value,
            "active": c.active,
            "starts_at": c.starts_at.isoformat() if c.starts_at else None,
            "ends_at": c.ends_at.isoformat() if c.ends_at else None,
        }
        for c in items
    ]
    # Optional: log to console without breaking response
    print("list_coupons called, count =", len(payload))

    return jsonify(api_ok("ok", payload)), 200
