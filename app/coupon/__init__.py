#  --- app/coupon/__init__.py ---

from flask import Blueprint
bp = Blueprint("coupon", __name__, url_prefix="/api/coupon")

from . import routes