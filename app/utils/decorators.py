# ------- app/utils/decorators.py -------
from functools import wraps
from flask import request, jsonify
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request

from app.cart.routes import api_error
from app.model.user import User

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

def role_required(*roles):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()

            uid = get_jwt_identity()
            try:
                uid_int = int(uid) if uid is not None else None
            except ValueError:
                uid_int = None

            user = User.query.get(uid_int) if uid_int else None
            if not user:
                return jsonify(api_error("Unauthorized")), 401

            if user.role not in roles:
                return jsonify(api_error("Forbidden")), 403

            return fn(*args, **kwargs)
        return wrapper
    return decorator