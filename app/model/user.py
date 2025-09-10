# --- app/models/user.py ---

from ..extensions import db

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name=db.Column(db.String(180), nullable=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(100), nullable=False,default="")
    role= db.Column(db.String(50), nullable=False, default="user", index=True) # roles: user, admin

    def as_dict(self):
        return {
            "id": self.id, 
            "email": self.email, 
            "name": self.name,
            "role": self.role
            }
    
class RefreshToken(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    token = db.Column(db.String(64), unique=True, nullable=False, index=True)
    expires_at = db.Column(db.DateTime, nullable=False)