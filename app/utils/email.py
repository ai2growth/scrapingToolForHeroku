# app/utils/email.py
from flask import current_app
from flask_mail import Message
from app.extensions import mail
from threading import Thread

def send_async_email(app, msg):
    with app.app_context():
        try:
            mail.send(msg)
        except Exception as e:
            app.logger.error(f"Failed to send email: {str(e)}")

def send_password_reset_email(user, reset_url):
    app = current_app._get_current_object()
    msg = Message(
        'Password Reset Request',
        sender=app.config['MAIL_DEFAULT_SENDER'],
        recipients=[user.email]
    )
    msg.body = f'''To reset your password, visit the following link:
{reset_url}

If you did not make this request, simply ignore this email and no changes will be made.
'''
    msg.html = f'''
    <p>To reset your password, click the following link:</p>
    <p><a href="{reset_url}">Reset Password</a></p>
    <p>If you did not make this request, simply ignore this email and no changes will be made.</p>
    '''
    Thread(target=send_async_email, args=(app, msg)).start()