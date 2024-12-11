from flask_login import UserMixin
from datetime import datetime
from .extensions import db

class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    scrape_limit = db.Column(db.Integer, default=20000)
    scrapes_used = db.Column(db.Integer, default=0)

    def update_scrape_count(self, rows_scraped):
        """Update the number of rows scraped by the user"""
        self.scrapes_used += rows_scraped
        db.session.commit()

    def __repr__(self):
        return f'<User {self.username}>'