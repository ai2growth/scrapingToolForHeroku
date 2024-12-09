from flask import Blueprint, render_template, jsonify, request, redirect, url_for, flash, current_app, send_file
from flask_login import login_required, current_user
from app.extensions import db
from app.models import User
from datetime import datetime, timedelta
import pandas as pd
import os

bp = Blueprint('admin', __name__, url_prefix='/admin')

@bp.route('/dashboard')
@login_required
def dashboard():
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('main.index'))
    
    users = User.query.all()
    return render_template('admin/dashboard.html', users=users)

@bp.route('/users')
@login_required
def list_users():
    if not current_user.is_admin:
        return jsonify({"error": "Unauthorized"}), 403
    
    users = User.query.all()
    return jsonify({
        "users": [{
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "is_admin": user.is_admin,
            "scrape_limit": user.scrape_limit,
            "scrapes_used": user.scrapes_used,
            "last_reset_date": user.last_reset_date.isoformat() if user.last_reset_date else None,
            "created_at": user.created_at.isoformat() if user.created_at else None
        } for user in users]
    })

@bp.route('/update_user_limit', methods=['POST'])
@login_required
def update_user_limit():
    if not current_user.is_admin:
        return jsonify({"error": "Unauthorized"}), 403

    data = request.json
    if not data or 'user_id' not in data or 'new_limit' not in data:
        return jsonify({"error": "Missing required fields"}), 400

    user = User.query.get(data['user_id'])
    if not user:
        return jsonify({"error": "User not found"}), 404

    try:
        user.scrape_limit = int(data['new_limit'])
        db.session.commit()
        return jsonify({
            "message": "User limit updated successfully",
            "user": {
                "id": user.id,
                "username": user.username,
                "scrape_limit": user.scrape_limit
            }
        })
    except ValueError:
        return jsonify({"error": "Invalid limit value"}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@bp.route('/reset_user_usage', methods=['POST'])
@login_required
def reset_user_usage():
    if not current_user.is_admin:
        return jsonify({"error": "Unauthorized"}), 403

    data = request.json
    if not data or 'user_id' not in data:
        return jsonify({"error": "Missing user_id"}), 400

    user = User.query.get(data['user_id'])
    if not user:
        return jsonify({"error": "User not found"}), 404

    try:
        user.scrapes_used = 0
        user.last_reset_date = datetime.utcnow()
        db.session.commit()
        return jsonify({
            "message": "User usage reset successfully",
            "user": {
                "id": user.id,
                "username": user.username,
                "scrapes_used": user.scrapes_used,
                "last_reset_date": user.last_reset_date.isoformat()
            }
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@bp.route('/user_usage/<int:user_id>')
@login_required
def get_user_usage(user_id):
    if not current_user.is_admin:
        return jsonify({"error": "Unauthorized"}), 403

    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    next_reset = user.last_reset_date + timedelta(days=30)
    days_until_reset = (next_reset - datetime.utcnow()).days

    return jsonify({
        "total_scrapes": user.scrapes_used,
        "last_30_days": user.scrapes_used,  # Since we reset every 30 days
        "remaining": user.scrape_limit - user.scrapes_used,
        "next_reset": next_reset.isoformat(),
        "days_until_reset": days_until_reset,
        "limit": user.scrape_limit
    })

@bp.route('/usage_summary')
@login_required
def usage_summary():
    if not current_user.is_admin:
        return jsonify({"error": "Unauthorized"}), 403

    try:
        total_users = User.query.count()
        active_users = User.query.filter(User.scrapes_used > 0).count()
        
        near_limit = db.session.query(User).filter(
            User.scrapes_used > (User.scrape_limit * 0.8)
        ).count()

        total_scrapes = db.session.query(db.func.sum(User.scrapes_used)).scalar() or 0
        avg_usage = db.session.query(db.func.avg(User.scrapes_used)).scalar() or 0

        return jsonify({
            "summary": {
                "total_users": total_users,
                "active_users": active_users,
                "users_near_limit": near_limit,
                "total_scrapes": total_scrapes,
                "average_usage": round(float(avg_usage), 2)
            }
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@bp.route('/edit_user/<int:user_id>', methods=['GET', 'POST'])
@login_required
def edit_user(user_id):
    if not current_user.is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('main.index'))

    user = User.query.get_or_404(user_id)

    if request.method == 'POST':
        try:
            user.username = request.form.get('username', user.username)
            user.email = request.form.get('email', user.email)
            user.scrape_limit = int(request.form.get('scrape_limit', user.scrape_limit))

            if current_user.id != user.id:
                user.is_admin = 'is_admin' in request.form

            new_password = request.form.get('new_password')
            if new_password:
                from app.extensions import bcrypt
                user.password = bcrypt.generate_password_hash(new_password).decode('utf-8')

            db.session.commit()
            flash('User updated successfully', 'success')
            return redirect(url_for('admin.dashboard'))

        except Exception as e:
            db.session.rollback()
            flash(f'Error updating user: {str(e)}', 'danger')

    return render_template('admin/edit_user.html', user=user)

@bp.route('/delete_user/<int:user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    if not current_user.is_admin:
        return jsonify({"error": "Unauthorized"}), 403

    if current_user.id == user_id:
        return jsonify({"error": "Cannot delete your own account"}), 400

    user = User.query.get_or_404(user_id)
    try:
        db.session.delete(user)
        db.session.commit()
        flash('User deleted successfully', 'success')
        return jsonify({"message": "User deleted successfully"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@bp.route('/bulk_action', methods=['POST'])
@login_required
def bulk_action():
    if not current_user.is_admin:
        return jsonify({"error": "Unauthorized"}), 403

    data = request.json
    if not data or 'action' not in data or 'user_ids' not in data:
        return jsonify({"error": "Missing required fields"}), 400

    action = data['action']
    user_ids = data['user_ids']

    try:
        users = User.query.filter(User.id.in_(user_ids)).all()
        
        if action == 'reset':
            for user in users:
                user.scrapes_used = 0
                user.last_reset_date = datetime.utcnow()
        
        elif action == 'update_limit':
            if 'new_limit' not in data:
                return jsonify({"error": "New limit not provided"}), 400
            new_limit = int(data['new_limit'])
            for user in users:
                user.scrape_limit = new_limit
        
        elif action == 'delete':
            for user in users:
                if user.id != current_user.id:
                    db.session.delete(user)
        
        else:
            return jsonify({"error": "Invalid action"}), 400

        db.session.commit()
        return jsonify({"message": f"Bulk {action} completed successfully"})

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@bp.route('/export_users')
@login_required
def export_users():
    if not current_user.is_admin:
        return jsonify({"error": "Unauthorized"}), 403

    try:
        users = User.query.all()
        data = [{
            'Username': user.username,
            'Email': user.email,
            'Is Admin': user.is_admin,
            'Scrape Limit': user.scrape_limit,
            'Scrapes Used': user.scrapes_used,
            'Last Reset': user.last_reset_date.strftime('%Y-%m-%d %H:%M:%S'),
            'Created At': user.created_at.strftime('%Y-%m-%d %H:%M:%S')
        } for user in users]

        df = pd.DataFrame(data)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"users_export_{timestamp}.csv"
        filepath = os.path.join(current_app.config['DOWNLOADS_FOLDER'], filename)
        
        df.to_csv(filepath, index=False)
        
        return send_file(
            filepath,
            mimetype='text/csv',
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500
