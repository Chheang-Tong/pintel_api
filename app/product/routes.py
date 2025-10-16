from flask import request, jsonify, url_for, current_app, send_file
from werkzeug.utils import secure_filename
from sqlalchemy.exc import IntegrityError
from sqlalchemy import or_, desc, asc
from ..extensions import db
from ..model import Product, ProductImage, Category
from ..utils.decorators import require_headers
from ..utils.api import api_ok, api_error
from . import bp
import os
import re
import pandas as pd
from datetime import datetime
from io import BytesIO

# ---------- helpers ----------
def _ep(name: str) -> str:
    return f"{bp.name}.{name}"

UPLOAD_FOLDER = "static/uploads"
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "gif", "webp"}

def slugify(text):
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")

def _allowed(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def _save_file(file_storage, product_name=None):
    """Save FileStorage to /static/uploads with product-name-based filename."""
    if not file_storage or not file_storage.filename:
        return None, None
    if not _allowed(file_storage.filename):
        raise ValueError("Unsupported file type")

    ext = os.path.splitext(secure_filename(file_storage.filename))[1].lower()
    filename = f"{slugify(product_name)}{ext}" if product_name else secure_filename(file_storage.filename)

    upload_dir = os.path.join(current_app.root_path, UPLOAD_FOLDER)
    os.makedirs(upload_dir, exist_ok=True)

    abs_path = os.path.join(upload_dir, filename)
    base, ext2 = os.path.splitext(filename)
    counter = 1
    while os.path.exists(abs_path):
        filename = f"{base}-{counter}{ext2}"
        abs_path = os.path.join(upload_dir, filename)
        counter += 1

    file_storage.save(abs_path)
    public_url = f"/{UPLOAD_FOLDER}/{filename}"
    return public_url, abs_path

def _parse_bool(v, default=False):
    if v is None:
        return default
    if isinstance(v, bool):
        return v
    return str(v).strip().lower() in {"1", "true", "yes", "y", "on"}

def _parse_int(v, default=0):
    try:
        return int(v)
    except Exception:
        return default
    
def _parse_opt_int(v):
    if v is None:
        return None
    if isinstance(v, str) and v.strip().lower() in {"", "null"}:
        return None
    try:
        return int(v)
    except Exception:
        return None

def _sort_products(query, sort):
    sort = (sort or "").strip()
    mapping = {
        "id": asc(Product.id),   "-id": desc(Product.id),
        "name": asc(Product.name), "-name": desc(Product.name),
        "price": asc(Product.price), "-price": desc(Product.price)
    }
    col = mapping.get(sort, desc(Product.id))  # default newest first (id desc)
    return query.order_by(col)


def _parse_float(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default

def _page_url(page, per_page):
    args = request.args.to_dict(flat=True)
    args["page"] = page
    args["per_page"] = per_page
    return url_for(_ep("list_products"), _external=True, **args)

def _paginate(query, page, per_page):
    page = max(_parse_int(page, 1), 1)
    per_page = min(max(_parse_int(per_page, 10), 1), 100)
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
# helpers (add these if not already present)
def _parse_opt_int(v):
    if v is None: return None
    if isinstance(v, str) and v.strip().lower() in {"", "null"}: return None
    try: return int(v)
    except Exception: return None

def _parse_opt_float(v):
    if v is None: return None
    if isinstance(v, str) and v.strip() == "": return None
    try: return float(v)
    except Exception: return None


# unified response helpers
def ok(message: str, data=None, status_code=200):
    resp = jsonify(api_ok(message, data))
    resp.status_code = status_code
    return resp

def err(message: str, status_code=400, data=None):
    resp = jsonify(api_error(message, data))
    resp.status_code = status_code
    return resp

def conflict(msg="Unique constraint violation", fields=None):
    return err(msg, status_code=409, data={"conflicts": fields} if fields else None)

def parse_unique_violation(err_exc: IntegrityError):
    m = re.search(r"UNIQUE constraint failed:\s*([^.]+)\.([^\s,]+)", str(err_exc.orig))
    if m:
        return {"table": m.group(1), "column": m.group(2)}
    m = re.search(r"Key \(([^)]+)\)=\(([^)]+)\) already exists", str(err_exc.orig))
    if m:
        col, val = m.group(1), m.group(2)
        return {"table": "product", "column": col, "value": val}
    return None

def format_price(value, symbol=None, decimals=2, use_thousands=True):
    try:
        n = float(value)
    except (TypeError, ValueError):
        n = 0.0
    symbol = symbol or getattr(current_app, "config", {}).get("CURRENCY_SYMBOL", "$")
    num = f"{n:,.{decimals}f}" if use_thousands else f"{n:.{decimals}f}"
    return f"{symbol}{num}"

# ---------- routes ----------
# GET /api/products
@bp.get("")
@require_headers
def list_products():
    
    """
    Query params:
      q            -> substring match on name/barcode; if q is an int, also match id
      barcode      -> exact barcode match (string)
      id           -> exact id match (int)
      ids          -> comma-separated ids, e.g. "1,3,9"
      min_price    -> float
      max_price    -> float
      in_stock     -> bool (true/false)  (True = stock > 0, False = stock <= 0)
      category_id  -> int
      sort         -> id, -id, name, -name, price, -price, stock, -stock
      page         -> int, default 1
      per_page     -> int, default 15 (cap 100)
    """

    q = (request.args.get("q") or "").strip()
    barcode = (request.args.get("barcode") or "").strip()
    want_id = _parse_opt_int(request.args.get("id"))
    ids_param = (request.args.get("ids") or "").strip()
    min_price = _parse_opt_float(request.args.get("min_price"))
    max_price = _parse_opt_float(request.args.get("max_price"))
    in_stock = _parse_bool(request.args.get("in_stock")) if request.args.get("in_stock") is not None else None
    category_id = _parse_opt_int(request.args.get("category_id"))
    sort = request.args.get("sort")
    page = request.args.get("page", default=1, type=int)
    per_page = request.args.get("per_page", default=15, type=int)
    per_page = max(1, min(per_page, 100))

    # choose correct stock/quantity column
    stock_col = getattr(Product, "stock", None) or getattr(Product, "quantity")

    query = Product.query

    # free text q (also try to match id if q is int)
    if q:
        maybe_id = _parse_opt_int(q)
        like = f"%{q}%"
        query = query.filter(
            or_(
                Product.name.ilike(like),
                Product.barcode.ilike(like),
                (Product.id == maybe_id) if maybe_id is not None else False,
            )
        )

    # exact barcode
    if barcode:
        query = query.filter(Product.barcode == barcode)

    # id / ids
    if want_id is not None:
        query = query.filter(Product.id == want_id)

    if ids_param:
        try:
            ids_list = [int(x) for x in ids_param.split(",") if x.strip() != ""]
            if ids_list:
                query = query.filter(Product.id.in_(ids_list))
        except ValueError:
            return err("Invalid ids parameter; must be comma-separated integers")

    # price range
    if min_price is not None:
        query = query.filter(Product.price >= min_price)
    if max_price is not None:
        query = query.filter(Product.price <= max_price)

    # stock flag
    if in_stock is True and stock_col is not None:
        query = query.filter(stock_col > 0)
    elif in_stock is False and stock_col is not None:
        query = query.filter(stock_col <= 0)

    # category
    if category_id is not None:
        query = query.filter(Product.category_id == category_id)

    # sort + paginate
    query = _sort_products(query, sort)
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    items = [p.as_api() for p in pagination.items]

    links = {
        "first": _page_url(1, per_page),
        "last": _page_url(pagination.pages or 1, per_page),
        "prev": _page_url(pagination.prev_num, per_page) if pagination.has_prev else None,
        "next": _page_url(pagination.next_num, per_page) if pagination.has_next else None,
    }

    meta = {
        "current_page": pagination.page,
        "from": (pagination.page - 1) * per_page + 1 if pagination.total > 0 else None,
        "last_page": pagination.pages or 1,
        "links": [
            {"url": _page_url(i, per_page), "label": str(i), "active": i == pagination.page}
            for i in range(1, (pagination.pages or 1) + 1)
        ],
        "path": url_for(_ep("list_products"), _external=True),
        "per_page": per_page,
        "to": (pagination.page - 1) * per_page + len(items) if pagination.total > 0 else None,
        "total": pagination.total,
    }

    return ok("Products fetched", {"items": items, "links": links, "meta": meta})

# GET /api/products/<id>
@bp.get("/<int:pid>")
@require_headers
def get_product(pid):
    product = Product.query.get_or_404(pid)
    return ok("Product fetched", product.as_api())

# POST /api/products
@bp.post("")
@require_headers
def create_product():
    is_multipart = request.content_type and "multipart/form-data" in request.content_type

    if is_multipart:
        form = request.form
        files = request.files
        barcode = form.get("barcode")
        name = form.get("name")
        if not barcode:
            return err("barcode are required")
        if not name:
            return err("name is required")
        category_id = form.get("category_id", type=int)
        category_id = _parse_int(category_id, default=None)
        product = Product(
            barcode=barcode,
            slug=form.get("slug"),
            name=name,
            code=form.get("code"),
            price=_parse_float(form.get("price")),
            price_format=None,
            quantity=_parse_int(form.get("quantity")),
            minimum_order=_parse_int(form.get("minimum_order", 1)),
            subtract_stock=form.get("subtract_stock", "yes"),
            out_of_stock_status=form.get("out_of_stock_status", "in_stock"),
            date_available=form.get("date_available"),
            sort_order=_parse_int(form.get("sort_order")),
            status=_parse_bool(form.get("status", "true"), True),
            is_new=_parse_bool(form.get("is_new")),
            viewed=_parse_int(form.get("viewed")),
            is_favourite=_parse_bool(form.get("is_favourite")),
            reviewable=_parse_bool(form.get("reviewable"), True),
            unit=form.get("unit"),
            ean_code=form.get("ean_code"),
            category_id = category_id
        )
        product.price_format = format_price(product.price, symbol=current_app.config.get("CURRENCY_SYMBOL", "$"), decimals=2)
        

        if "image" in files and files["image"].filename:
            try:
                public_url, _ = _save_file(files["image"], product_name=product.name)
                product.images.append(ProductImage(name="main", image_path=public_url, main=True, image_url=public_url))
            except ValueError as e:
                return err(str(e))

        for key, fs in files.items():
            if key.startswith("image_") and fs.filename:
                try:
                    public_url, _ = _save_file(fs, product_name=product.name)
                    product.images.append(ProductImage(name=key, image_path=public_url, main=False, image_url=public_url))
                except ValueError as e:
                    return err(str(e))

    else:
        data = request.get_json(silent=True) or {}
        barcode = data.get("barcode")
        name = data.get("name")
        if not barcode or not name:
            return err("barcode are required")
        if not name:
            return err("name is required")

        product = Product(
            barcode=barcode,
            slug=data.get("slug"),
            name=name,
            code=data.get("code"),
            price=_parse_float(data.get("price")),
            price_format=None,
            quantity=_parse_int(data.get("quantity")),
            minimum_order=_parse_int(data.get("minimum_order", 1)),
            subtract_stock=data.get("subtract_stock", "yes"),
            out_of_stock_status=data.get("out_of_stock_status", "in_stock"),
            date_available=data.get("date_available"),
            sort_order=_parse_int(data.get("sort_order")),
            status=_parse_bool(data.get("status", True), True),
            is_new=_parse_bool(data.get("is_new")),
            viewed=_parse_int(data.get("viewed")),
            is_favourite=_parse_bool(data.get("is_favourite")),
            reviewable=_parse_bool(data.get("reviewable"), True),
            unit=data.get("unit"),
            ean_code=data.get("ean_code"),
            category_id = _parse_int(data.get("category_id"))
        )
        product.price_format = format_price(product.price, symbol=current_app.config.get("CURRENCY_SYMBOL", "$"), decimals=2)

        for img in (data.get("images") or []):
            product.images.append(ProductImage(
                name=img.get("name") or "image",
                image_path=img.get("image_path") or img.get("image_url"),
                main=_parse_bool(img.get("main")),
                image_url=img.get("image_url") or img.get("image_path"),
            ))

    try:
        db.session.add(product)
        db.session.commit()
    except IntegrityError as e:
        db.session.rollback()
        info = parse_unique_violation(e)
        if info:
            submitted = {}
            if info.get("column") == "code":
                submitted["code"] = request.form.get("code") if request.form else (request.json or {}).get("code")
            if info.get("column") == "barcode":
                submitted["barcode"] = request.form.get("barcode") if request.form else (request.json or {}).get("barcode")
            return conflict(msg=f"Duplicate {info['column']}", fields={info["column"]: submitted.get(info["column"])})
        return conflict("Duplicate or invalid data")

    resp = ok("Product created", product.as_api(), status_code=201)
    resp.headers["Location"] = url_for(_ep("get_product"), pid=product.id, _external=True)
    return resp

# PUT /api/products/<id>
@bp.put("/<int:pid>")
@require_headers
def update_product(pid):
    product = Product.query.get_or_404(pid)

    is_multipart = request.content_type and "multipart/form-data" in request.content_type
    data = {}

    if is_multipart:
        form = request.form
        data = form.to_dict(flat=True)

        files = request.files
        if any(k.startswith("image") for k in files.keys()) or "images" in data:
            product.images.clear()

            if "image" in files and files["image"].filename:
                try:
                    public_url, _ = _save_file(files["image"], product_name=product.name)
                    product.images.append(ProductImage(name="main", image_path=public_url, main=True, image_url=public_url))
                except ValueError as e:
                    return err(str(e))

            for key, fs in files.items():
                if key.startswith("image_") and fs.filename:
                    try:
                        public_url, _ = _save_file(fs, product_name=product.name)
                        product.images.append(ProductImage(name=key, image_path=public_url, main=False, image_url=public_url))
                    except ValueError as e:
                        return err(str(e))
    else:
        data = request.get_json(force=True, silent=True) or {}
        if "images" in data:
            product.images.clear()
            for img in data["images"]:
                product.images.append(ProductImage(
                    name=img.get("name") or "image",
                    image_path=img.get("image_path") or img.get("image_url"),
                    main=_parse_bool(img.get("main")),
                    image_url=img.get("image_url") or img.get("image_path"),
                ))

    # --- category update: normalize, validate, assign ---
    if "category_id" in data:
        cid = _parse_opt_int(data.get("category_id"))
        if cid is None:
            product.category_id = None
        else:
            cat = Category.query.get(cid)
            if not cat:
                return err(f"Category {cid} not found", status_code=404)
            product.category_id = cid

    # assign fields (do NOT accept price_format from client)
    price_updated = False
    for field, caster in [
        ("barcode", str), ("slug", str), ("name", str), ("code", str),
        ("price", _parse_float),
        ("quantity", _parse_int), ("minimum_order", _parse_int),
        ("subtract_stock", str), ("out_of_stock_status", str),
        ("date_available", str), ("sort_order", _parse_int),
        ("status", _parse_bool), ("is_new", _parse_bool), ("viewed", _parse_int),
        ("is_favourite", _parse_bool), ("reviewable", _parse_bool),
        ("is_pin", _parse_bool),
        ("unit", str), ("ean_code", str),
        # NOTE: intentionally omit ("category_id", _parse_int)
    ]:
        if field in data and data[field] is not None:
            try:
                setattr(product, field, caster(data[field]))
                if field == "price":
                    price_updated = True
            except Exception:
                return err(f"Invalid value for {field}")

    if price_updated:
        product.price_format = format_price(
            product.price, symbol=current_app.config.get("CURRENCY_SYMBOL", "$"), decimals=2
        )

    try:
        db.session.commit()
    except IntegrityError as e:
        db.session.rollback()
        info = parse_unique_violation(e)
        if info:
            submitted = {}
            if info.get("column") == "code":
                submitted["code"] = (data.get("code") if data else None)
            if info.get("column") == "barcode":
                submitted["barcode"] = (data.get("barcode") if data else None)
            return conflict(msg=f"Duplicate {info['column']}", fields={info["column"]: submitted.get(info["column"])})
        return err("Duplicate or invalid data", status_code=400, data={"detail": str(e.orig)})

    return ok("Product updated", product.as_api())

# DELETE /api/products/<id>
@bp.delete("/<int:pid>")
@require_headers
def delete_product(pid):
    product = Product.query.get_or_404(pid)
    try:
        db.session.delete(product)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return err("Failed to delete product", status_code=500, data={"detail": str(e)})
    return ok(f"Product {pid} deleted", {"id": pid})

# PATCH /api/products/<id>/favorite
@bp.route("/<int:pid>/favorite", methods=["PATCH", "POST"])
@require_headers
def set_favorite(pid):
    product = Product.query.get_or_404(pid)
    payload = request.get_json(silent=True) or {}
    product.is_favourite = _parse_bool(payload.get("value")) if "value" in payload else (not product.is_favourite)
    try:
        db.session.commit()
    except IntegrityError as e:
        db.session.rollback()
        return err("Failed to update favorite", data={"detail": str(e.orig)})
    return ok("Favorite updated", product.as_api())

# PATCH /api/products/<id>/pin
@bp.route("/<int:pid>/pin", methods=["PATCH", "POST"])
@require_headers
def set_pin(pid):
    product = Product.query.get_or_404(pid)
    payload = request.get_json(silent=True) or {}
    product.is_pin = _parse_bool(payload.get("value")) if "value" in payload else (not product.is_pin)
    try:
        db.session.commit()
    except IntegrityError as e:
        db.session.rollback()
        return err("Failed to update pin", data={"detail": str(e.orig)})
    return ok("Pin updated", product.as_api())
@bp.get("/export")
@require_headers
def export_products():
    """
    Export all products as an Excel file.
    """
    products = Product.query.all()
    product_data = [{
        "Barcode": p.barcode,
        "Slug": p.slug,
        "Name": p.name,
        "Code": p.code,
        "Price": p.price,
        "Quantity": p.quantity,
        "Minimum Order": p.minimum_order,
        "Subtract Stock": p.subtract_stock,
        "Out of Stock Status": p.out_of_stock_status,
        "Date Available": p.date_available,
        "Status": p.status,
        "Is New": p.is_new,
        "Viewed": p.viewed,
        "Is Favourite": p.is_favourite,
        "Reviewable": p.reviewable,
        "Unit": p.unit,
        "EAN Code": p.ean_code,
        "Category ID": p.category_id,
    } for p in products]
    df = pd.DataFrame(product_data)

    # Create an in-memory buffer
    output = BytesIO()
    df.to_excel(output, index=False)
    output.seek(0)

    return send_file(
        output, 
        as_attachment=True, 
        download_name="products_export.xlsx", 
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

@bp.post("/import")
@require_headers
def import_products():
    """
    Import products from an uploaded .xlsx file.
    """
    if "file" not in request.files:
        return err("No file part", status_code=400)
    
    file = request.files["file"]
    if file.filename == "":
        return err("No selected file", status_code=400)

    if not file.filename.endswith(".xlsx"):
        return err("Only .xlsx files are allowed", status_code=400)

    try:
        # Read the uploaded Excel file into a pandas DataFrame
        df = pd.read_excel(file)

        # Validate the columns
        required_columns = ['Barcode', 'Slug', 'Name', 'Code', 'Price', 'Quantity', 'Minimum Order', 
                            'Subtract Stock', 'Out of Stock Status', 'Date Available', 'Status', 
                            'Is New', 'Viewed', 'Is Favourite', 'Reviewable', 'Unit', 'EAN Code', 'Category ID']
        if not all(col in df.columns for col in required_columns):
            return err("Missing required columns in the uploaded file", status_code=400)

        # Insert products into the database
        for _, row in df.iterrows():
    # Convert date to string in YYYY-MM-DD format
            date_available = row['Date Available']
            if pd.notnull(date_available):
                if isinstance(date_available, pd.Timestamp):
                    date_available = date_available.strftime("%Y-%m-%d")
                elif isinstance(date_available, str):
                    # optional: validate string format
                    try:
                        datetime.strptime(date_available, "%Y-%m-%d")
                    except ValueError:
                        return err(f"Invalid date format for {row['Name']}")
            else:
                date_available = None

            product = Product(
                barcode=row['Barcode'],
                slug=row['Slug'],
                name=row['Name'],
                code=row['Code'],
                price=row['Price'],
                quantity=row['Quantity'],
                minimum_order=row['Minimum Order'],
                subtract_stock=row['Subtract Stock'],
                out_of_stock_status=row['Out of Stock Status'],
                date_available=date_available,  # <--- use the converted string
                status=row['Status'],
                is_new=row['Is New'],
                viewed=row['Viewed'],
                is_favourite=row['Is Favourite'],
                reviewable=row['Reviewable'],
                unit=row['Unit'],
                ean_code=row['EAN Code'],
                category_id=row['Category ID']
            )
            db.session.add(product)



        # Commit the changes to the database
        db.session.commit()

        return ok("Products imported successfully", status_code=200)
    except Exception as e:
        db.session.rollback()
        return err(f"Error importing products: {str(e)}", status_code=500)