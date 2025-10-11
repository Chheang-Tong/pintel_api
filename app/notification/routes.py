from flask import jsonify, request

from ..model import Notification
from . import bp
from ..extensions import db

@bp.get("")
def index():
    return jsonify({"message": "Notification Service is running"})
@bp.post("")
def create_notification():
    data = request.json
    new_note = Notification(user_id=data["user_id"], message=data["message"])
    db.session.add(new_note)
    db.session.commit()
    return jsonify({"message": "Notification created"}), 201
@bp.get("/<int:user_id>")
def get_notifications(user_id):
    notes = Notification.query.filter_by(user_id=user_id).all()
    return jsonify([{
        "id": n.id,
        "message": n.message,
        "is_read": n.is_read
    } for n in notes])

@bp.put("/<int:note_id>/read")
def mark_as_read(note_id):
    note = Notification.query.get_or_404(note_id)
    note.is_read = True
    db.session.commit()
    return jsonify({"message": "Marked as read"})
