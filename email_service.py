import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def send_email(subject, body, to_email):
    """Sends an email using SMTP."""
    # These should be configured securely, e.g., through environment variables
    sender_email = "arunprojectcse@gmail.com"  # <-- REPLACE WITH YOUR EMAIL
    password = "fedceeiaixnumrtb"  # <-- REPLACE WITH YOUR GMAIL APP PASSWORD

    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'html'))

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, password)
        text = msg.as_string()
        server.sendmail(sender_email, to_email, text)
        server.quit()
        print("Email sent successfully!")
    except Exception as e:
        print(f"Failed to send email: {e}")