from flask import request, jsonify, current_app
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity,create_refresh_token
from datetime import datetime, timedelta
from . import bp
from ..model import User, RefreshToken
from ..extensions import db 
from ..utils.api import api_ok, api_error
from ..utils.decorators import require_headers
import uuid


# --- helper: create & persist a token pair ---
def _issue_tokens(user_id: int, access_ttl_hours: int = 1, refresh_ttl_days: int = 7):
    access_token = create_access_token(
        identity=str(user_id),
        expires_delta=timedelta(hours=access_ttl_hours),
    )
    refresh_token_str = str(uuid.uuid4())
    refresh_row = RefreshToken(
        user_id=user_id,
        token=refresh_token_str,
        expires_at=datetime.utcnow() + timedelta(days=refresh_ttl_days),
    )
    db.session.add(refresh_row)
    return access_token, refresh_token_str

@bp.post("/register")
@require_headers
def register():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    name =(data.get("name")or"").strip()

    if not email :
        return jsonify(api_error("Email required")), 400
    if not password or len(password) < 6:
        return jsonify(api_error("Password required, min 6 chars")), 400
    if not name:
        return jsonify(api_error("Api Error")), 400
    if User.query.filter_by(email=email).first():
        return jsonify(api_error('Email already registered')), 409

    user = User(
        email=email, 
        password_hash=generate_password_hash(password),
        name=name
        )
    db.session.add(user)
    db.session.commit()
    
    return jsonify(api_ok(
        "Account created successfully",
        data={
            "user": user.as_dict(),
            "user_logged_in": True,
        })), 201

@bp.post("/login")
@require_headers
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    user = User.query.filter_by(email=email).first()
    if not email or not password:
        return jsonify(api_error("Email and password are required")), 400
    if not user or not check_password_hash(user.password_hash, password):
        return jsonify(api_error("Invalid email or password")), 401

    access_token = create_access_token(identity=str(user.id))

    token_str = str(uuid.uuid4())
    refresh = RefreshToken(
        user_id=user.id,
        token=token_str,
        expires_at=datetime.utcnow() + timedelta(days=7)
    )
    db.session.add(refresh)
    db.session.commit()

    return jsonify(api_ok(
        "You've logged in successfully",
        data={
            "user": user.as_dict(),
            "user_logged_in": True,
            "token": access_token,
            "refresh_token": token_str
        }
    )), 200
    
@bp.get("/me")
@jwt_required()
def me_alias():
    uid = get_jwt_identity()  
    user = User.query.get(int(uid))
    if not user:
        return jsonify(api_error("user not found")), 404
    return jsonify(user=user.as_dict())

@bp.get("/headers")
def get_headers():
    headers = {
        "Content-Type": request.headers.get("Content-Type"),
        "Accept": request.headers.get("Accept"),
        "Platform": request.headers.get("Platform"),
        "Accept-Language": request.headers.get("Accept-Language"),
        "Ocp-Apim-Subscription-Key": request.headers.get("Ocp-Apim-Subscription-Key"),
    }
    return jsonify(headers)


@bp.post("/refresh")
@require_headers
def refresh():
    data = request.get_json(silent=True) or {}
    token_str = data.get("refresh_token")
    if not token_str:
        return jsonify(api_error("refresh_token is required")), 400

    # Look up the presented refresh token
    refresh_row = RefreshToken.query.filter_by(token=token_str).first()

    # Reject if missing or expired
    if not refresh_row or refresh_row.expires_at < datetime.utcnow():
        return jsonify(api_error("Invalid or expired refresh token")), 401

    user_id = refresh_row.user_id

    # ROTATE: make the old refresh token single-use by removing it
    db.session.delete(refresh_row)
    db.session.flush()  # ensures the delete happens before new insert

    # Issue a brand-new pair
    new_access, new_refresh = _issue_tokens(user_id)
    db.session.commit()

    return jsonify(api_ok(
        "Token refreshed",
        data={
            "token": new_access,
            "refresh_token": new_refresh
        }
    )), 200