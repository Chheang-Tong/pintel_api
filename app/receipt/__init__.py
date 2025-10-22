#  --- app/receipt/__init__.py ---

from flask import Blueprint
bp = Blueprint("receipt", __name__, url_prefix="/api/receipt")

from . import routes