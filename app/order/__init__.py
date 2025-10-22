#  --- app/order/__init__.py ---

from flask import Blueprint
bp = Blueprint("order", __name__, url_prefix="/api/order")

from . import routes