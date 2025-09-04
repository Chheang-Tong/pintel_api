from flask import Blueprint
bp = Blueprint("categories", __name__, url_prefix="/api/categories")

from . import routes 