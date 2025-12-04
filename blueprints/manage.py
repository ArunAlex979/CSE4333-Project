import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, jsonify, session
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
from functools import wraps
from blueprints.auth import admin_required

manage_bp = Blueprint('manage', __name__, url_prefix='/manage/data')

@manage_bp.route('/')
@admin_required
def manage_list():
    stations_ref = current_app.db.collection(u'stations').where(u'deleted', u'!=', True).stream()
    active_sites = []
    for doc in stations_ref:
        site = doc.to_dict()
        site['id'] = doc.id
        active_sites.append(site)
    return render_template('manage_list.html', sites=active_sites)

@manage_bp.route('/trash')
@admin_required
def manage_trash():
    stations_ref = current_app.db.collection(u'stations').where(u'deleted', u'==', True).stream()
    deleted_sites = []
    for doc in stations_ref:
        site = doc.to_dict()
        site['id'] = doc.id
        deleted_sites.append(site)
    return render_template('manage_trash.html', sites=deleted_sites)

@manage_bp.route('/add', methods=['GET', 'POST'])
@admin_required
def manage_add():
    if request.method == 'POST':
        try:
            name = request.form['name']
            start_date = request.form['start_date']
            end_date = request.form['end_date']
            latitude = request.form['latitude']
            longitude = request.form['longitude']
            site_comments = request.form['site_comments']
            counts_str = request.form.getlist('counts[]')
            counts = [int(c) for c in counts_str if c.strip()]
            date_increment = request.form['date_increment']

            labels, current_index, _ = current_app.generate_labels_and_current_index(date_increment)

            future_counts_were_non_zero = False
            for i in range(current_index + 1, len(labels)):
                if i < len(counts) and counts[i] != 0:
                    future_counts_were_non_zero = True
                    counts[i] = 0

            if not name:
                flash('Site Name is required.', 'error')
            elif not start_date or not end_date:
                flash('Start Date and End Date are required.', 'error')
            elif len(counts) != len(labels):
                flash(f'Counts must be exactly {len(labels)} numbers for the selected increment.', 'error')
            elif any(c < 0 for c in counts):
                flash('Vehicle counts cannot be negative.', 'error')
            else:
                battery_level = int(request.form.get('battery_level', 100))
                new_site = {
                    u"name": name,
                    u"counts": counts,
                    u"start_date": start_date,
                    u"end_date": end_date,
                    u"deleted": False,
                    u"latitude": latitude,
                    u"longitude": longitude,
                    u"site_comments": site_comments,
                    u"date_increment": date_increment,
                    u"battery_level": battery_level
                }
                current_app.db.collection(u'stations').add(new_site)
                flash('Site added successfully!', 'success')
                if future_counts_were_non_zero:
                    flash('Note: Data for future dates was automatically set to zero.', 'info')
                return redirect(url_for('manage.manage_list'))
        except ValueError:
            flash('Invalid number format in counts or battery level.', 'error')
        except Exception as e:
            flash(f'An error occurred: {e}', 'error')

    default_site = {
        "name": "New Site",
        "counts": [0]*24,
        "start_date": datetime.now().strftime('%Y-%m-%d'),
        "end_date": (datetime.now() + timedelta(days=365)).strftime('%Y-%m-%d'),
        "latitude": "",
        "longitude": "",
        "site_comments": "",
        "date_increment": "bimonthly",
        "battery_level": 100
    }
    labels, current_index, _ = current_app.generate_labels_and_current_index(default_site['date_increment'])
    return render_template('manage_add.html', site=default_site, labels=labels, current_index=current_index)

@manage_bp.route('/<id>/edit', methods=['GET', 'POST'])
@admin_required
def manage_edit(id):
    doc_ref = current_app.db.collection(u'stations').document(id)
    site = doc_ref.get()
    if not site.exists:
        return "Site not found", 404
    site = site.to_dict()

    if request.method == 'POST':
        try:
            name = request.form['name']
            start_date = request.form['start_date']
            end_date = request.form['end_date']
            latitude = request.form['latitude']
            longitude = request.form['longitude']
            site_comments = request.form['site_comments']
            counts_str = request.form.getlist('counts[]')
            counts = [int(c) for c in counts_str if c.strip()]
            date_increment = request.form['date_increment']

            labels, current_index, _ = current_app.generate_labels_and_current_index(date_increment)

            future_counts_were_non_zero = False
            for i in range(current_index + 1, len(labels)):
                if i < len(counts) and counts[i] != 0:
                    future_counts_were_non_zero = True
                    counts[i] = 0

            if not name:
                flash('Site Name is required.', 'error')
            elif not start_date or not end_date:
                flash('Start Date and End Date are required.', 'error')
            elif len(counts) != len(labels):
                flash(f'Counts must be exactly {len(labels)} numbers for the selected increment.', 'error')
            elif any(c < 0 for c in counts):
                flash('Vehicle counts cannot be negative.', 'error')
            else:
                battery_level = int(request.form.get('battery_level', site.get('battery_level', 100)))
                update_data = {
                    u'name': name,
                    u'counts': counts,
                    u'start_date': start_date,
                    u'end_date': end_date,
                    u'latitude': latitude,
                    u'longitude': longitude,
                    u'site_comments': site_comments,
                    u'date_increment': date_increment,
                    u'battery_level': battery_level
                }
                doc_ref.update(update_data)
                flash('Site updated successfully!', 'success')
                if future_counts_were_non_zero:
                    flash('Note: Data for future dates was automatically set to zero.', 'info')
                return redirect(url_for('manage.manage_list'))
        except ValueError:
            flash('Invalid number format in counts or battery level.', 'error')
        except Exception as e:
            flash(f'An error occurred: {e}', 'error')

    labels, current_index, _ = current_app.generate_labels_and_current_index(site.get('date_increment', 'bimonthly'))
    return render_template('manage_edit.html', site=site, labels=labels, current_index=current_index, id=id)

@manage_bp.route('/<id>/delete', methods=['POST'])
@admin_required
def manage_delete(id):
    try:
        doc_ref = current_app.db.collection(u'stations').document(id)
        doc_ref.update({u'deleted': True})
        flash('Site moved to trash.', 'success')
    except Exception as e:
        flash(f'Error moving site to trash: {e}', 'error')
    return redirect(url_for('manage.manage_list'))

@manage_bp.route('/<id>/restore', methods=['POST'])
@admin_required
def manage_restore(id):
    try:
        doc_ref = current_app.db.collection(u'stations').document(id)
        doc_ref.update({u'deleted': False})
        flash('Site restored successfully.', 'success')
    except Exception as e:
        flash(f'Error restoring site: {e}', 'error')
    return redirect(url_for('manage.manage_trash'))



@manage_bp.route('/get_labels_and_index/<date_increment>')
@admin_required
def get_labels_and_index(date_increment):
    labels, current_index, _ = current_app.generate_labels_and_current_index(date_increment)
    return jsonify(labels=labels, current_index=current_index)

@manage_bp.route('/reset-future-counts', methods=['POST'])
@admin_required
def reset_future_counts():
    try:
        stations_ref = current_app.db.collection(u'stations').where(u'deleted', u'!=', True).stream()
        for site in stations_ref:
            site_dict = site.to_dict()
            date_increment = site_dict.get('date_increment', 'bimonthly')
            labels, current_index, _ = current_app.generate_labels_and_current_index(date_increment)
            
            updated_counts = list(site_dict.get('counts', []))
            
            # Set future counts to zero
            for i in range(current_index + 1, len(labels)):
                if i < len(updated_counts):
                    updated_counts[i] = 0

            site.reference.update({u'counts': updated_counts})
        flash('Future counts reset to zero for all active sites.', 'success')
        return jsonify(success=True)
    except Exception as e:
        flash(f'Error resetting future counts: {e}', 'error')
        return jsonify(success=False, error=str(e)), 500