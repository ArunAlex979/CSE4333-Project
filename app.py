import os
from flask import Flask, render_template, redirect, url_for, flash, current_app
from google.cloud import firestore

# Initialize Firestore client
db = firestore.Client()

def load_data():
    stations_ref = db.collection(u'stations')
    docs = stations_ref.stream()
    data = [doc.to_dict() for doc in docs]
    # Sanitize counts: ensure no negative values
    for site in data:
        if 'counts' in site and isinstance(site['counts'], list):
            site['counts'] = [max(0, c) for c in site['counts']]
    return data

def save_data(data):
    stations_ref = db.collection(u'stations')
    # This is not efficient for large datasets, but it's a simple way to keep the data in sync.
    # For a production application, you would want to update documents individually.
    for station in data:
        doc_ref = stations_ref.document(station['id'])
        doc_ref.set(station)

app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config['TIMEZONE'] = 'America/Chicago'


# Make the database object available to the app context
app.db = db


# Ensure uploads directory exists
upload_folder = os.path.join(app.root_path, 'static', 'uploads')
os.makedirs(upload_folder, exist_ok=True)

# Load data on startup
with app.app_context():
    current_app.data = load_data()

app.save_data_func = save_data # Make save_data accessible to blueprints

from datetime import date, datetime, timedelta
import pytz

def generate_labels_and_current_index(date_increment="bimonthly", year=None):
    labels = []
    timezone = pytz.timezone(current_app.config['TIMEZONE'])
    current_date = datetime.now(timezone)
    if year is None:
        year = current_date.year

    current_index = -1
    last_data_datetime = None

    is_leap = (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0)
    days_in_year = 366 if is_leap else 365

    if date_increment == "daily":
        for i in range(days_in_year):
            d = datetime(year, 1, 1) + timedelta(days=i)
            labels.append(d.strftime('%b %d'))
            if d.date() == current_date.date():
                current_index = i
                last_data_datetime = d
    elif date_increment == "weekly":
        for i in range(52):
            d = datetime(year, 1, 1) + timedelta(weeks=i)
            labels.append(f"Week {i+1} ({d.strftime('%b %d')})")
            if d.isocalendar()[1] == current_date.isocalendar()[1] and d.year == year:
                current_index = i
                last_data_datetime = d
    elif date_increment == "monthly":
        for month in range(1, 13):
            d = date(year, month, 1)
            labels.append(d.strftime('%b'))
            if current_date.year == year and current_date.month == month:
                current_index = month - 1
                last_data_datetime = datetime(d.year, d.month, d.day)
    elif date_increment == "bimonthly":
        for month in range(1, 13):
            date1 = date(year, month, 1)
            labels.append(f"{date1.day} {date1.strftime('%b')}")
            if current_date.year == year and current_date.month == month and current_date.day < 15:
                current_index = len(labels) - 1
                last_data_datetime = datetime(date1.year, date1.month, date1.day)

            date2 = date(year, month, 15)
            labels.append(f"{date2.day} {date2.strftime('%b')}")
            if current_date.year == year and current_date.month == month and current_date.day >= 15:
                current_index = len(labels) - 1
                last_data_datetime = datetime(date2.year, date2.month, date2.day)
    return labels, current_index, last_data_datetime

app.generate_labels_and_current_index = generate_labels_and_current_index

def get_next_collection_timestamp(date_increment="bimonthly", last_data_date=None):
    timezone = pytz.timezone(current_app.config['TIMEZONE'])
    now = last_data_date if last_data_date else datetime.now(timezone)
    year = now.year
    next_collection_date = None

    if date_increment == "daily":
        next_collection_date = now + timedelta(days=1)
    elif date_increment == "weekly":
        next_collection_date = now + timedelta(weeks=1)
    elif date_increment == "monthly":
        if now.month == 12:
            next_collection_date = datetime(year + 1, 1, 1)
        else:
            next_collection_date = datetime(year, now.month + 1, 1)
    elif date_increment == "bimonthly":
        if now.day >= 15:
            if now.month == 12:
                next_collection_date = datetime(year + 1, 1, 1)
            else:
                next_collection_date = datetime(year, now.month + 1, 1)
        else:
            next_collection_date = datetime(year, now.month, 15)

    return int(next_collection_date.timestamp() * 1000)

app.get_next_collection_timestamp = get_next_collection_timestamp # This will be called dynamically

# Register blueprints
from blueprints.home import home_bp
from blueprints.site import site_bp
from blueprints.manage import manage_bp
from blueprints.summary import summary_bp
from blueprints.email_settings import email_settings_bp
from blueprints.logs import logs_bp
from blueprints.api import api_bp
from blueprints.auth import auth_bp

app.register_blueprint(home_bp)
app.register_blueprint(site_bp)
app.register_blueprint(manage_bp)
app.register_blueprint(summary_bp)
app.register_blueprint(email_settings_bp)
app.register_blueprint(logs_bp)
app.register_blueprint(api_bp)
app.register_blueprint(auth_bp)

if __name__ == '__main__':
    app.run(debug=False)


