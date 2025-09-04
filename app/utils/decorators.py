# ------- app/utils/decorators.py -------
from functools import wraps
from flask import request, jsonify

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