#  --- app/cart/__init__.py ---

from flask import Blueprint
bp = Blueprint("cart", __name__, url_prefix="/api/cart")

from . import routes