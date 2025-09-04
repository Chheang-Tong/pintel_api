from flask import Blueprint
bp = Blueprint("products", __name__,url_prefix="/api/products")

from . import routes 