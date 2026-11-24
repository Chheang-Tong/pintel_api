# app/cli.py
import click
from werkzeug.security import generate_password_hash
from .extensions import db
from .model import User

@click.command("create-admin")
@click.option("--email", required=True)
@click.option("--password", required=True)
@click.option("--name", required=True)
def create_admin(email, password, name):
    email = email.strip().lower()
    if User.query.filter_by(email=email).first():
        click.echo("Email already exists"); return
    u = User(email=email, name=name, password_hash=generate_password_hash(password), role="admin")
    db.session.add(u); db.session.commit()
    click.echo(f"Admin created: {u.id} {u.email}")

def register_cli(app):
    app.cli.add_command(create_admin)
