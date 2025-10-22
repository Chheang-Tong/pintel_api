from flask import request, jsonify, current_app
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity,create_refresh_token
from datetime import datetime, timedelta
import os
from . import bp
from ..model import User, RefreshToken
from ..extensions import db 
from ..utils.api import api_ok, api_error
from ..utils.decorators import _current_user, require_headers, role_at_least, role_required
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
@jwt_required(optional=True)   # allow no-token public signups, but honor role only if privileged
def register():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    name = (data.get("name") or "").strip()

    if not email:
        return jsonify(api_error("Email required")), 400
    if not password or len(password) < 6:
        return jsonify(api_error("Password required, min 6 chars")), 400
    if not name:
        return jsonify(api_error("Api Error")), 400
    if User.query.filter_by(email=email).first():
        return jsonify(api_error("Email already registered")), 409

    # Bootstrap: very first account becomes admin
    is_first_user = db.session.query(User.id).count() == 0
    role = "admin" if is_first_user else "user"

    # Admin-only override; managers can create users (forced)
    requested_role = (data.get("role") or "user").strip().lower()
    allowed = {"user", "manager", "admin"}
    caller_id = get_jwt_identity()
    if not is_first_user and caller_id:
        try: caller = User.query.get(int(caller_id))
        except: caller = None
        if caller and caller.role == "admin" and requested_role in allowed:
            role = requested_role
        elif caller and caller.role == "manager":
            role = "user"   # managers can only create users

    user = User(email=email, password_hash=generate_password_hash(password), name=name, role=role)
    db.session.add(user)
    db.session.commit()

    return jsonify(api_ok("Account created successfully", data={"user": user.as_dict(), "user_logged_in": True})), 201

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
    access_token, token_str = _issue_tokens(user.id)

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
@bp.get("/admin/dashboard")
@role_required("admin")   # single role
def admin_dashboard():
    return {"msg": "Welcome Admin!"}

@bp.get("/manager/report")
@role_required("admin", "manager")   # multiple roles
def manager_report():
    return {"msg": "Admins & Managers can see this"}

@bp.patch("/users/<int:user_id>/role")
@role_required("admin")
def update_user_role(user_id):
    actor = _current_user()  # from decorators.py
    body = request.get_json(silent=True) or {}
    new_role = (body.get("role") or "").strip().lower()
    if new_role not in {"user", "admin", "manager"}:
        return jsonify(api_error("Invalid role")), 400

    target = User.query.get(user_id)
    if not target:
        return jsonify(api_error("User not found")), 404

    # Admin can manage managers & users; can also manage admins, but…
    # Prevent demoting the LAST admin
    if target.role == "admin" and new_role != "admin":
        admin_count = db.session.query(User).filter_by(role="admin").count()
        if admin_count <= 1:
            return jsonify(api_error("Cannot demote the last admin")), 400

    target.role = new_role
    db.session.commit()
    return jsonify(api_ok("Role updated", data={"user": target.as_dict()})), 200


@bp.get("/reports")
@role_at_least("manager")
def manager_reports():
    return {"msg": "Managers only"}

@bp.get("/settings")
@role_required("admin")
def admin_settings():
    return {"msg": "Admins only"}

@bp.get("/users")
@role_at_least("manager", message="Only managers and admins can list users")
def list_users():
    actor = _current_user()
    q = User.query
    if actor.role == "manager":
        q = q.filter(User.role == "user")
    items = [u.as_dict() for u in q.order_by(User.id.asc()).all()]
    return jsonify(api_ok("OK", data={"users": items})), 200

@bp.delete("/users/<int:user_id>")
@role_at_least("manager")
def delete_user(user_id):
    actor = _current_user()
    target = User.query.get(user_id)
    if not target:
        return jsonify(api_error("User not found")), 404

    # Managers can manage only users; admins can manage managers+users
    if actor.role == "manager" and target.role != "user":
        return jsonify(api_error("Forbidden: managers may delete users only")), 403

    # Admin cannot remove the last admin
    if target.role == "admin":
        admin_count = db.session.query(User).filter_by(role="admin").count()
        if admin_count <= 1:
            return jsonify(api_error("Cannot delete the last admin")), 400

    db.session.delete(target)
    db.session.commit()
    return jsonify(api_ok("User deleted")), 200
