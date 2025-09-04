# --- category/routes.py ---
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from sqlalchemy import or_, asc, desc
from ..model import Category, Product
from ..extensions import db
from app.utils.decorators import require_headers
from . import bp
# ------------------------ helpers ------------------------
def _to_int(v, default=None):
    try: 
        return int(v)
    except (TypeError, ValueError): 
        return default

def _paginate(query, page, per_page):
    page = max(_to_int(page, 1), 1)
    per_page = min(max(_to_int(per_page, 10), 1), 100)
    items = query.paginate(page=page, per_page=per_page, error_out=False)
    return {
        "meta": {
            "page": items.page,
            "pages": items.pages or 1,
            "per_page": per_page,
            "total": items.total,
        },
        "items": items.items,
    }
# ------------------------ CATEGORY ROUTES ------------------------

@bp.post("/")
@require_headers
@jwt_required()
def create_category():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify(msg="name required"), 400
    if Category.query.filter(Category.name.ilike(name)).first():
        return jsonify(msg="category name already exists"), 409
    c = Category(name=name)
    db.session.add(c)
    db.session.commit()
    return jsonify(category=c.as_dict()), 201


@bp.get("/")
@require_headers
@jwt_required()
def list_categories():
    """
    q        -> substring match on name
    sort     -> name, -name, id, -id
    page     -> default 1
    per_page -> default 10 (cap 100)
    """
    q = (request.args.get("q") or "").strip()
    sort = (request.args.get("sort") or "name").strip()
    page = request.args.get("page")
    per_page = request.args.get("per_page")

    qry = Category.query
    if q:
        qry = qry.filter(Category.name.ilike(f"%{q}%"))

    sort_map = {
        "id": Category.id,
        "-id": desc(Category.id),
        "name": Category.name,
        "-name": desc(Category.name),
    }
    qry = qry.order_by(sort_map.get(sort, Category.name))
    page_data = _paginate(qry, page, per_page)

    return jsonify(
        meta=page_data["meta"],
        categories=[c.as_dict() for c in page_data["items"]],
    )

@bp.get("/<int:cid>")
@require_headers
@jwt_required()
def get_category(cid):
    c = Category.query.get_or_404(cid)
    return jsonify(category=c.as_dict())


@bp.put("/<int:cid>")
@require_headers
@jwt_required()
def update_category(cid):
    c = Category.query.get_or_404(cid)
    data = request.get_json(silent=True) or {}
    if "name" in data:
        new_name = (data.get("name") or "").strip()
        if not new_name:
            return jsonify(msg="name cannot be empty"), 400
        exists = Category.query.filter(
            Category.name.ilike(new_name), Category.id != c.id
        ).first()
        if exists:
            return jsonify(msg="category name already exists"), 409
        c.name = new_name
    db.session.commit()
    return jsonify(category=c.as_dict())


@bp.delete("/<int:cid>")
@require_headers
@jwt_required()
def delete_category(cid):
    if Product.query.filter_by(category_id=cid).first():
        return jsonify(msg="cannot delete: category has products"), 409
    c = Category.query.get_or_404(cid)
    db.session.delete(c)
    db.session.commit()
    return jsonify(msg="deleted"), 200