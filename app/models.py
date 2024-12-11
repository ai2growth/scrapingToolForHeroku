from datetime import datetime, timedelta
from flask_login import UserMixin
from app.extensions import db
import secrets

class User(UserMixin, db.Model):
    __tablename__ = 'users'  # Make sure this is 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    reset_token = db.Column(db.String(100), unique=True)
    reset_token_expiry = db.Column(db.DateTime)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    scrape_limit = db.Column(db.Integer, default=20000)
    scrapes_used = db.Column(db.Integer, default=0)

    def get_reset_token(self, expires_in=3600):
        """Generate a password reset token that expires in 1 hour"""
        self.reset_token = secrets.token_urlsafe(32)
        self.reset_token_expiry = datetime.utcnow() + timedelta(seconds=expires_in)
        db.session.commit()
        return self.reset_token

    @staticmethod
    def verify_reset_token(token):
        """Verify the reset token and return the user if valid"""
        user = User.query.filter_by(reset_token=token).first()
        if user is None or user.reset_token_expiry < datetime.utcnow():
            return None
        return user

    def update_scrape_count(self, rows_scraped):
        """Update the number of rows scraped by the user"""
        self.scrapes_used += rows_scraped
        if self.scrapes_used > self.scrape_limit:
            raise ValueError("Scrape limit exceeded")
        db.session.commit()

    def __repr__(self):
        return f'<User {self.username}>'
