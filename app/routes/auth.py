import logging
from datetime import datetime
from flask import Blueprint, render_template, url_for, flash, redirect, request, current_app
from flask_login import login_user, logout_user, login_required, current_user
from app.models import User, db
from app.utils import send_password_reset_email
from app.utils.password import PasswordHasher
from app.forms import LoginForm, RegisterForm, ForgotPasswordForm, ResetPasswordForm

logger = logging.getLogger(__name__)

bp = Blueprint('auth', __name__)

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    form = LoginForm()
    if form.validate_on_submit():
        try:
            user = User.query.filter_by(email=form.email.data).first()
            
            if user and user.check_password(form.password.data):
                login_user(user)
                next_page = request.args.get('next')
                flash('Login successful!', 'success')
                return redirect(next_page or url_for('main.index'))
            else:
                flash('Invalid email or password', 'danger')
        except Exception as e:
            logger.error(f"Login error: {str(e)}")
            flash('An error occurred during login', 'danger')
            
    return render_template('auth/login.html', form=form)

@bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully.', 'info')
    return redirect(url_for('auth.login'))

@bp.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    form = ForgotPasswordForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            token = user.get_reset_token()
            reset_url = url_for('auth.reset_password', token=token, _external=True)
            try:
                send_password_reset_email(user, reset_url)
                flash('Password reset instructions have been sent to your email.', 'info')
            except Exception as e:
                current_app.logger.error(f"Failed to send password reset email: {str(e)}")
                flash('Error sending password reset email. Please try again later.', 'danger')
            return redirect(url_for('auth.login'))
        
        flash('If an account exists with that email, a password reset link has been sent.', 'info')
        return redirect(url_for('auth.login'))

    return render_template('auth/forgot_password.html', form=form)

@bp.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    user = User.query.filter_by(reset_token=token).first()
    if not user or user.reset_token_expiry < datetime.utcnow():
        flash('Invalid or expired reset link.', 'danger')
        return redirect(url_for('auth.forgot_password'))

    form = ResetPasswordForm()
    if form.validate_on_submit():
        if form.password.data != form.confirm_password.data:
            flash('Passwords do not match.', 'danger')
            return render_template('auth/reset_password.html', form=form)

        user.password = PasswordHasher.generate_password_hash(form.password.data)
        user.reset_token = None
        user.reset_token_expiry = None
        db.session.commit()

        flash('Your password has been reset successfully.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/reset_password.html', form=form)

@bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    form = RegisterForm()
    if form.validate_on_submit():
        try:
            # Check if user already exists
            if User.query.filter_by(username=form.username.data).first():
                flash('Username already exists. Please choose a different one.', 'danger')
                return render_template('auth/register.html', form=form)
            
            if User.query.filter_by(email=form.email.data).first():
                flash('Email already registered. Please use a different one.', 'danger')
                return render_template('auth/register.html', form=form)
            
            # Create new user
            hashed_password = PasswordHasher.generate_password_hash(form.password.data)
            user = User(
                username=form.username.data,
                email=form.email.data,
                password=hashed_password,
                scrape_limit=20000  # Default scrape limit
            )
            
            db.session.add(user)
            db.session.commit()
            
            flash('Your account has been created! You can now log in.', 'success')
            return redirect(url_for('auth.login'))
            
        except Exception as e:
            logger.error(f"Error during registration: {str(e)}")
            db.session.rollback()
            flash('An error occurred during registration. Please try again.', 'danger')
            
    return render_template('auth/register.html', form=form)

# Error handlers
@bp.errorhandler(404)
def not_found_error(error):
    return render_template('errors/404.html'), 404

@bp.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('errors/500.html'), 500
