from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
import gspread
from flask import Flask, render_template, request, redirect, url_for, make_response, session, jsonify
from wtforms import FileField
from werkzeug.utils import secure_filename
import os
import uuid
import time
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import google.auth
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from io import BytesIO

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SESSION_TYPE'] = 'filesystem'  # You can use other session types as well

# Configure Google Sheets API credentials
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive','https://www.googleapis.com/auth/drive.file','https://www.googleapis.com/auth/drive.metadata.readonly']
SCOPES = ['https://www.googleapis.com/auth/drive.file','https://www.googleapis.com/auth/drive.metadata.readonly']

# Load credentials directly from the JSON file
creds = 'just-hook-410317-a3de29623f8f.json'  # Replace with the actual path to your credentials file

client = gspread.service_account(filename=creds)
SERVICE_ACCOUNT_FILE = 'just-hook-410317-a3de29623f8f.json'

credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES
)

drive_service = build('drive', 'v3', credentials=credentials)

# Forms
class LoginForm(FlaskForm):
    email = StringField('Email')
    password = PasswordField('Password')
    submit = SubmitField('Login')

class UploadForm(FlaskForm):
    files = FileField('Files', render_kw={"multiple": True})
    submit = SubmitField('Upload Files')  # Add a submit button

    def __init__(self, email, *args, **kwargs):
        super(UploadForm, self).__init__(*args, **kwargs)
        self.email = email

# Function to get the folder id for the given folder name
def get_folder_id_by_name(folder_name):
    folder_list = drive_service.files().list(
        q=f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    ).execute().get('files', [])

    print(f'Folder list for {folder_name}: {folder_list}')

    if folder_list:
        return folder_list[0]['id']
    else:
        return None

# Function to check user credentials and return user information
def check_credentials(email, password):
    # Google Sheet containing user credentials
    user_sheet = client.open('Users').sheet1
    users = user_sheet.get_all_records()
    for user in users:
        if 'email' in user and 'password' in user and user['email'] == email and user['password'] == password:
            print(f'Successful login for email: {email}')
            return user  # Return user information upon successful authentication
    print(f'Login failed for email: {email}')
    return None

# Function to set user authentication flag in cookies
def set_auth_flag(email):
    response = make_response()
    print(f"Setting email cookie: {email}")
    response.set_cookie('Email', email)
    response.set_cookie('Authenticated', 'true')  # Set a flag to indicate authentication
    return response

# Function to get user information from cookies
def get_user_from_cookies():
    email = request.cookies.get('Email')
    authenticated = request.cookies.get('Authenticated')
    print(f"Retrieved email from cookies: {email}")
    return {'email': email, 'authenticated': authenticated}

# Routes
@app.route('/download')
def download_files():
    # Google Sheet containing file details
    file_sheet = client.open('Document Links').sheet1
    file_data = file_sheet.get_all_records()
    return render_template('download.html', file_data=file_data)

# Handle file upload
@app.route('/upload', methods=['GET', 'POST'])
def upload_files():
    form = UploadForm(email=request.cookies.get('Email'))
    email = request.cookies.get('Email')
    print(f"Email from cookies: {email}")
    TARGET_FOLDER_ID = get_folder_id_by_name(email)

    if request.method == 'POST':
        try:
            uploaded_file = request.files['file']
            print(f"Target Folder ID: {TARGET_FOLDER_ID}")

            if uploaded_file:
                try:
                    # Upload the file to Google Drive
                    file_metadata = {'name': uploaded_file.filename, 'parents': [TARGET_FOLDER_ID]}
                    media_body = MediaIoBaseUpload(BytesIO(uploaded_file.read()), mimetype=uploaded_file.mimetype)

                    uploaded_file_info = drive_service.files().create(
                        body=file_metadata,
                        media_body=media_body,
                        fields='id'
                    ).execute()

                    print(f'File uploaded successfully! File ID: {uploaded_file_info["id"]}')
                except Exception as e:
                    print(f'Error during file upload: {e}')
                    uploaded_file_info = None

                print(f'API Response: {uploaded_file_info}')

            return render_template('upload.html', form=form)
        except Exception as e:
            print(f'Error uploading file: {e}')
            return f'Error uploading file: {e}'

    return render_template('upload.html', form=form)

# Use the 'before_request' decorator to run this function before each request
@app.before_request
def before_request():
    # If the request is for the home or login page, allow it
    if request.endpoint in ['home', 'dashboard']:
        return

    # If the user is not authenticated, redirect to the login page
    if 'user' not in session:
        return redirect(url_for('home'))

@app.route('/')
def home():
    form = LoginForm()  # Create an instance of the form
    return render_template('login.html', form=form)

# Modify the login route to store user information in session upon successful login
@app.route('/dashboard', methods=['POST', 'GET'])
def dashboard():
    form = LoginForm()

    if request.method == 'POST' and form.validate_on_submit():
        email = form.email.data
        password = form.password.data

        user_info = check_credentials(email, password)
        if user_info:
            # Successful login, store user information in session
            session['user'] = user_info
            return redirect(url_for('dashboard_page', email=email))
        else:
            # Incorrect credentials, render the login page with an error message
            error_message = "Incorrect credentials. Please contact Pranav if you want access."
            return render_template('login.html', error_message=error_message, form=form)

    # If it's a GET request or other cases, render the login page
    return render_template('login.html', form=form)

@app.route('/logout')
def logout():
    # Clear the user's session and redirect to the login page
    session.clear()
    return redirect(url_for('home'))

@app.route('/dashboard_page')
def dashboard_page():
    email = request.args.get('email')
    if email:
        response = make_response(render_template('dashboard.html', email=email))
        response.set_cookie('Email', email)
        response.set_cookie('Authenticated', 'true')
        return response
    else:
        return redirect(url_for('home'))


if __name__ == "__main__":
    app.run(debug=True)
