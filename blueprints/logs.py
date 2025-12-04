from flask import Blueprint, render_template, current_app
from datetime import datetime
from google.cloud import firestore
from blueprints.auth import login_required

logs_bp = Blueprint('logs', __name__, url_prefix='/logs')

@logs_bp.route('/')
@login_required
def view_logs():
    us_timezones = [
        'America/New_York',
        'America/Chicago',
        'America/Denver',
        'America/Los_Angeles',
        'America/Anchorage',
        'America/Honolulu'
    ]
    return render_template('logs.html', timezones=us_timezones, current_timezone=current_app.config['TIMEZONE'])
