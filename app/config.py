import os

class Config:
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JSON_SORT_KEYS = False
    ENV = os.getenv("FLASK_ENV", "development")
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "dev-secret-change-me")

    @staticmethod
    def init_app(app):
        
        if not os.getenv("DATABASE_URL"):
            os.makedirs(app.instance_path, exist_ok=True)
            app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{os.path.join(app.instance_path, 'app.db')}"
        else:
            app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL")
# import os

# class Config:
   
#     SQLALCHEMY_DATABASE_URI = "sqlite:///"
#     SQLALCHEMY_TRACK_MODIFICATIONS = False

#     # JWT
#     JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "dev-secret-change-me")