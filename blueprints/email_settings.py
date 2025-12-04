import email_service
from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app
from blueprints.auth import admin_required

email_settings_bp = Blueprint('email_settings', __name__, url_prefix='/email-settings')

# Use a consistent document ID for settings
SETTINGS_DOC_ID = 'settings'

@email_settings_bp.route('/', methods=['GET', 'POST'])
@admin_required
def settings():
    settings_ref = current_app.db.collection(u'email_settings').document(SETTINGS_DOC_ID)
    
    if request.method == 'POST':
        # Get data from the form
        recipient_emails_str = request.form.get('recipient_emails')
        recipient_emails = [email.strip() for email in recipient_emails_str.replace(',', '\n').splitlines() if email.strip()]
        report_frequency = request.form.get('report_frequency', 'weekly')
        day_of_week = request.form.get('day_of_week')
        day_of_month = request.form.get('day_of_month')
        report_time = request.form.get('report_time')
        
        # Basic validation
        if not recipient_emails:
            flash('Recipient email(s) cannot be empty.', 'error')
        else:
            # Update or insert the settings
            settings_data = {
                u'recipient_emails': recipient_emails,
                u'report_frequency': report_frequency,
                u'day_of_week': day_of_week,
                u'day_of_month': day_of_month,
                u'report_time': report_time
            }
            settings_ref.set(settings_data)
            flash('Email settings saved successfully!', 'success')
            
            # Send notification email about the change
            from email_service import send_email
            subject = "TRAFx Email Settings Changed"
            body = f"""
            <p>Dear User,</p>
            <p>This is to confirm that the TRAFx email report settings have been updated:</p>
            <ul>
                <li><strong>Recipient Email(s):</strong> {', '.join(recipient_emails)}</li>
                <li><strong>Report Frequency:</strong> {report_frequency.capitalize()}</li>
            </ul>
            <p>You will now receive reports according to these new settings.</p>
            <p>Sincerely,<br>The TRAFx System</p>
            """
            for email in recipient_emails:
                email_service.send_email(subject, body, email)
            
        return redirect(url_for('email_settings.settings'))
    else: # GET request
        current_settings = settings_ref.get()
        if not current_settings.exists:
            # Provide default values if nothing is in the database yet
            current_settings = {
                'recipient_emails': ['youremail@example.com'],
                'report_frequency': 'weekly'
            }
        else:
            current_settings = current_settings.to_dict()
            
        return render_template('email_settings.html', settings=current_settings)
