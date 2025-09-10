# ------- app/utils/decorators.py -------
from functools import wraps
from flask import request, jsonify
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request

from ..utils.api import api_error
from ..model.user import User

def require_headers(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        required_headers = [
            "Content-Type",
            "Accept",
            "Platform",
            "Accept-Language",
            "Ocp-Apim-Subscription-Key",
        ]
        missing = [h for h in required_headers if not request.headers.get(h)]
        if missing:
            return jsonify(msg=f"Missing required headers: {', '.join(missing)}"), 400
        return f(*args, **kwargs)
    return wrapper

ROLE_LEVEL = {"user": 1, "manager": 2, "admin": 3}

def _current_user():
    verify_jwt_in_request()
    uid = get_jwt_identity()
    try:
        uid = int(uid)
    except (TypeError, ValueError):
        uid = None
    return User.query.get(uid) if uid else None

def role_required(*roles): # only manager or admin
    """Your existing decorator is fine; here is a robust version."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            u = _current_user()
            if not u:
                return jsonify(api_error("Unauthorized")), 401
            if u.role not in roles:
                return jsonify(api_error("Forbidden")), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator

def role_at_least(min_role: str): # admin > manager > user
    """Gate an endpoint by minimum role (e.g., manager or admin)."""
    min_level = ROLE_LEVEL[min_role]
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            u = _current_user()
            if not u:
                return jsonify(api_error("Unauthorized")), 401
            if ROLE_LEVEL.get(u.role, 0) < min_level:
                return jsonify(api_error("Forbidden")), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator

def can_manage(actor: User, target: User) -> bool:
    """Strictly greater role can manage lower role; equals/higher are blocked."""
    if not actor or not target:
        return False
    return ROLE_LEVEL[actor.role] > ROLE_LEVEL[target.role]
