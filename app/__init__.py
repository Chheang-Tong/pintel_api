# --- app/__init__.py ---
import os
from flask import Flask, jsonify
from .extensions import db, jwt, cors, migrate
from datetime import timedelta

def create_app():
    app = Flask(__name__, instance_relative_config=True)

    app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024
    app.config["UPLOAD_SUBDIR"] = "static/uploads"

    os.makedirs(app.instance_path, exist_ok=True)
    db_path = os.path.join(app.instance_path, "app.db")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("SQLALCHEMY_DATABASE_URI",f"sqlite:///{db_path}",)
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["JWT_SECRET_KEY"] = os.environ.get("JWT_SECRET_KEY", "dev-secret-change-me")
    app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(days=1)
    app.config["JWT_REFRESH_TOKEN_EXPIRES"] = timedelta(days=30)

    # Init extensions
    db.init_app(app)
    jwt.init_app(app)
    cors.init_app(app, resources={r"/*": {"origins": "*"}})
    migrate.init_app(app, db)

    # Register blueprints
    from .auth import bp as auth_bp; app.register_blueprint(auth_bp)
    from .product import bp as product_bp; app.register_blueprint(product_bp)
    from .category import bp as category_bp; app.register_blueprint(category_bp)
    from .cart import bp as cart_bp; app.register_blueprint(cart_bp)

    @app.get("/")
    def health():
        return jsonify(ok=True, msg="API running")

    with app.app_context():
        import importlib
        import app as apppkg

        base = os.path.dirname(apppkg.__file__)
        print("=== DEBUG FS ===")
        print("app dir:", base)
        try:
            print("app listdir:", sorted(os.listdir(base)))
        except Exception as e:
            print("listdir failed:", e)

        cart_path = os.path.join(base, "cart")
        print("cart dir exists?", os.path.isdir(cart_path))
        if os.path.isdir(cart_path):
            print("cart listdir:", sorted(os.listdir(cart_path)))

        print("=== DEBUG IMPORTS ===")
        try:
            cartpkg = importlib.import_module("app.cart")
            print("import app.cart OK:", cartpkg)
            print("has bp?", hasattr(cartpkg, "bp"))
            if hasattr(cartpkg, "bp"):
                print("bp.url_prefix:", cartpkg.bp.url_prefix)
        except Exception as e:
            print("import app.cart FAILED:", repr(e))

        print("=== BLUEPRINTS ===", sorted(app.blueprints.keys()))
        print("=== URL MAP ===")
        for rule in app.url_map.iter_rules():
            print(sorted(rule.methods), rule.rule)
        db.create_all()

    return app