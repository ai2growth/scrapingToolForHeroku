from app import create_app
from app.extensions import db, bcrypt
from app.models import User
import click

app = create_app()

@click.group()
def cli():
    pass

@cli.command()
@click.option('--email', prompt='Email address', help='User email address')
@click.option('--password', prompt=True, hide_input=True, confirmation_prompt=True, help='New password')
def set_password(email, password):
    """Set a new password for a user"""
    with app.app_context():
        user = User.query.filter_by(email=email).first()
        if user:
            user.password = bcrypt.generate_password_hash(password).decode('utf-8')
            db.session.commit()
            click.echo(f'Password updated for {email}')
        else:
            click.echo(f'No user found with email {email}')

@cli.command()
@click.option('--email', prompt='Email address', help='User email address')
@click.option('--username', prompt='Username', help='Username')
@click.option('--password', prompt=True, hide_input=True, confirmation_prompt=True, help='Password')
@click.option('--admin', is_flag=True, help='Make user an admin')
def create_user(email, username, password, admin):
    """Create a new user"""
    with app.app_context():
        if User.query.filter_by(email=email).first():
            click.echo(f'User with email {email} already exists')
            return
        if User.query.filter_by(username=username).first():
            click.echo(f'User with username {username} already exists')
            return
        
        user = User(
            email=email,
            username=username,
            password=bcrypt.generate_password_hash(password).decode('utf-8'),
            is_admin=admin
        )
        db.session.add(user)
        db.session.commit()
        click.echo(f'User created successfully: {email}')

if __name__ == '__main__':
    cli()