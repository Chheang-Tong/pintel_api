# app/coupon/service.py
from datetime import datetime, timezone
from sqlalchemy import func
from ..extensions import db
from ..utils.api import api_ok, api_error
from ..model import Coupon

def _parse_iso8601(s):
    if not s: return None
    s = s.strip()
    if s.endswith("Z"): s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo:
            return dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    except Exception:
        return None

def create_coupon_from_payload(data: dict):
    code = (data.get("code") or "").strip()
    ctype = (data.get("ctype") or "percent").lower().strip()
    try:
        value = float(data.get("value") or 0)
    except Exception:
        return api_error("value must be numeric"), 400

    active = bool(data.get("active", True))
    min_subtotal = data.get("min_subtotal")
    max_uses = data.get("max_uses")
    max_uses_per_cart = data.get("max_uses_per_cart", 1)
    stackable = bool(data.get("stackable", True))

    if not code:
        return api_error("code is required"), 400
    if ctype not in ("percent", "fixed"):
        return api_error("ctype must be 'percent' or 'fixed'"), 400
    if value <= 0:
        return api_error("value must be > 0"), 400

    existing = Coupon.query.filter(func.lower(Coupon.code) == code.lower()).first()
    if existing:
        return api_error("Coupon code already exists"), 400

    starts_at = _parse_iso8601(data.get("starts_at"))
    ends_at   = _parse_iso8601(data.get("ends_at"))
    if data.get("starts_at") and not starts_at:
        return api_error("Invalid datetime format for starts_at"), 400
    if data.get("ends_at") and not ends_at:
        return api_error("Invalid datetime format for ends_at"), 400

    c = Coupon(
        code=code, ctype=ctype, value=value, active=active,
        min_subtotal=min_subtotal, max_uses=max_uses,
        max_uses_per_cart=max_uses_per_cart, stackable=stackable,
        starts_at=starts_at, ends_at=ends_at,
    )
    db.session.add(c)
    db.session.commit()

    return api_ok("Coupon created", {
        "id": c.id, "code": c.code, "ctype": c.ctype,
        "value": c.value, "active": c.active
    }), 201
