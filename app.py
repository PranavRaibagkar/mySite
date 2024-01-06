from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
import gspread
from flask import Flask, render_template, request, redirect, url_for, make_response, session
from wtforms import FileField
from werkzeug.utils import secure_filename
import os
import uuid
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import google.auth
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive



app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['SESSION_TYPE'] = 'filesystem'  # You can use other session types as well


# Configure Google Sheets API credentials
scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']

# Load credentials directly from the JSON file
creds = 'just-hook-410317-a3de29623f8f.json'  # Replace with the actual path to your credentials file

client = gspread.service_account(filename=creds)


#just-hook-410317-a3de29623f8f
# Google Sheet containing user credentials
user_sheet = client.open('Users').sheet1

# Google Sheet containing file details
file_sheet = client.open('Document Links').sheet1

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


# Your Google Drive API credentials file
gauth = GoogleAuth()
gauth.LocalWebserverAuth()
drive = GoogleDrive(gauth)

# Make drive a global variable
drive = GoogleDrive(gauth)

# Routes

@app.route('/download')
def download_files():
    file_data = file_sheet.get_all_records()
    return render_template('download.html', file_data=file_data)

@app.route('/upload', methods=['GET', 'POST'])
def upload_files():
    form = UploadForm(email=request.cookies.get('Email'))

    if request.method == 'POST' and form.validate_on_submit():
        email = request.cookies.get('Email')
        user_folder_id = get_user_folder_id(email)

        # Upload each file to the user's folder
        for uploaded_file in request.files.getlist('files'):
            handle_file_uploads(request.files.getlist('files'), user_folder_id)

        return redirect(url_for('upload_files'))  # Adjust as needed

    return render_template('upload.html', form=form)

def get_user_files_count(email):
    # Implement logic to get the number of files associated with the user from Google Sheets
    # You may use gspread or any other library to interact with Google Sheets
    # Example:
    # user_files_sheet = client.open('UserFiles').sheet1
    # num_files = len(user_files_sheet.findall(email))  # Assuming the email is stored in the sheet

    # Replace this with your actual logic to get the number of files
    num_files = 3  # Example number of files

    return num_files

# Function to get the user's folder ID or create a new one
def get_user_folder_id(email):
    user_folder_name = secure_filename(email) if email else 'default_folder'

    # Check if the user folder already exists
    query = f"title='{user_folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    folder_list = drive.ListFile({'q': query}).GetList()

    if folder_list:
        # Return the ID of the existing folder
        return folder_list[0]['id']
    else:
        # Create a new folder and return its ID
        try:
            user_folder = drive.CreateFile({'title': user_folder_name, 'mimeType': 'application/vnd.google-apps.folder'})
            user_folder.Upload()
            print("Folder created successfully")
        except Exception as e:
            print(f"Error creating folder: {e}")
        return user_folder['id']

import time


# Function to handle file uploads
def handle_file_uploads(files, folder_id):
    # Create a unique temporary folder for each upload
    user_temp_folder = str(uuid.uuid4())
    temp_folder_path = os.path.join('temp', user_temp_folder)

    # Create the temporary folder if it doesn't exist
    os.makedirs(temp_folder_path, exist_ok=True)

    for uploaded_file in files:
        file_title = secure_filename(uploaded_file.filename)
        file_path = os.path.join(temp_folder_path, file_title)

        print(f"Saving file to temporary folder: {file_path}")

        uploaded_file.save(file_path)

        # Check if the file is saved with the correct size
        print(f"File size in temporary folder: {os.path.getsize(file_path)} bytes")

        # Upload the file to the user's folder
        file_drive = drive.CreateFile({'title': file_title, 'parents': [{'id': folder_id}]})
        # Use SetContentFile to directly set the content for upload
        file_drive.SetContentFile(file_path)

        # Upload the file
        file_drive.Upload()

        # Add logging to check the file size after upload
        print(f"File uploaded to Google Drive with size: {file_drive['fileSize']} bytes")

        # Delete the temporary file after upload
        try:
            os.remove(file_path)
            print(f"Temporary file deleted: {file_path}")
        except Exception as e:
            print(f"Error deleting temporary file: {e}")

    # Remove the temporary folder after all files are uploaded
    try:
        os.rmdir(temp_folder_path)
        print(f"Temporary folder deleted: {temp_folder_path}")
    except Exception as e:
        print(f"Error deleting temporary folder: {e}")


# Function to check user credentials and return user information
def check_credentials(email, password):
    users = user_sheet.get_all_records()

    for user in users:
        if 'email' in user and 'password' in user and user['email'] == email and user['password'] == password:
            return user  # Return user information upon successful authentication

    return None


# Function to set user authentication flag in cookies
def set_auth_flag(email):
    response = make_response()
    response.set_cookie('Email', email)
    response.set_cookie('Authenticated', 'true')  # Set a flag to indicate authentication
    return response

# Function to get user information from cookies
def get_user_from_cookies():
    email = request.cookies.get('Email')
    authenticated = request.cookies.get('Authenticated')
    return {'email': email, 'authenticated': authenticated}

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
            return redirect(url_for('dashboard_page'))
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
    return render_template('dashboard.html')

if __name__ == "__main__":
    app.run(debug=True)
