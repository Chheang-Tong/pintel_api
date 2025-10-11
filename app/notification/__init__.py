from flask import Blueprint
bp = Blueprint("notification", __name__,url_prefix="/api/notification")

from . import routes 