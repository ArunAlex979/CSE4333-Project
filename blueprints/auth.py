from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from google.cloud import firestore
from functools import wraps

db = firestore.Client()

auth_bp = Blueprint('auth', __name__, template_folder='templates')

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session and session.get('role') != 'guest':
            flash('You must be logged in to view this page.', 'danger')
            session['next'] = request.url
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('You must be logged in to view this page.', 'danger')
            return redirect(url_for('auth.login'))
        if session.get('role') != 'admin':
            flash('You do not have permission to access this page.', 'danger')
            return redirect(url_for('home.home'))
        return f(*args, **kwargs)
    return decorated_function

@auth_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']

        if not username or not password:
            flash('Username and password are required.', 'danger')
            return redirect(url_for('auth.signup'))

        users_ref = db.collection('users')
        query = users_ref.where('username', '==', username).limit(1).stream()

        if len(list(query)) > 0:
            flash('Username already exists.', 'danger')
            return redirect(url_for('auth.signup'))

        if role == 'admin':
            access_code = request.form.get('access_code')
            if not access_code:
                flash('Access code is required for admin role.', 'danger')
                return redirect(url_for('auth.signup'))

            access_code_ref = db.collection('access_codes').document(access_code)
            access_code_doc = access_code_ref.get()

            if not access_code_doc.exists or access_code_doc.to_dict().get('used'):
                flash('Invalid or used access code.', 'danger')
                return redirect(url_for('auth.signup'))

            access_code_ref.update({'used': True})

        hashed_password = generate_password_hash(password)
        users_ref.add({
            'username': username,
            'password': hashed_password,
            'role': role
        })

        flash('You have successfully signed up! Please login.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('signup.html')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if not username or not password:
            flash('Username and password are required.', 'danger')
            return redirect(url_for('auth.login'))

        users_ref = db.collection('users')
        query = users_ref.where('username', '==', username).limit(1).stream()
        user_list = list(query)

        if len(user_list) == 0:
            flash('Invalid username or password.', 'danger')
            return redirect(url_for('auth.login'))

        user = user_list[0].to_dict()

        if not check_password_hash(user['password'], password):
            flash('Invalid username or password.', 'danger')
            return redirect(url_for('auth.login'))

        session['user_id'] = user_list[0].id
        session['username'] = user['username']
        session['role'] = user.get('role', 'reader')

        flash('You have successfully logged in!', 'success')
        next_page = session.pop('next', None)
        if next_page:
            return redirect(next_page)
        return redirect(url_for('home.home'))

    return render_template('login.html')

@auth_bp.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'success')
    return redirect(url_for('auth.login'))

@auth_bp.route('/guest')
def guest_login():
    session['role'] = 'guest'
    session['username'] = 'Guest'
    return redirect(url_for('home.home'))