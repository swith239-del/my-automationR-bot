from flask import Flask, render_template, request, jsonify
from requests.auth import HTTPBasicAuth
import requests
import os
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
import atexit
import urllib3

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'your-secret-key-here')

# Store current session credentials
current_credentials = {
    'username': None,
    'password': None
}

scheduler = BackgroundScheduler()
scheduler.start()
atexit.register(lambda: scheduler.shutdown())

@app.route('/')
def dashboard():
    return render_template('index.html')

@app.route('/api/login', methods=['POST'])
def login():
    """Handle user login"""
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({'success': False, 'message': 'Username and password required'}), 400
    
    # Test credentials by making a request to the target API
    try:
        response = requests.get(
            'https://elog.pedc.ir/api/submit',
            auth=HTTPBasicAuth(username, password),
            verify=False,
            timeout=10
        )
        
        if response.status_code in [200, 401, 403]:  # Valid response (auth check)
            current_credentials['username'] = username
            current_credentials['password'] = password
            return jsonify({'success': True, 'message': 'Login successful'}), 200
        else:
            return jsonify({'success': False, 'message': f'Authentication failed: {response.status_code}'}), 401
    
    except Exception as e:
        return jsonify({'success': False, 'message': f'Connection error: {str(e)}'}), 500

@app.route('/api/submit', methods=['POST'])
def submit_data():
    """Submit data to elog.pedc.ir"""
    
    if not current_credentials['username'] or not current_credentials['password']:
        return jsonify({'success': False, 'message': 'Please login first'}), 401
    
    data = request.json
    
    try:
        response = requests.post(
            'https://elog.pedc.ir/api/submit',
            json=data,
            auth=HTTPBasicAuth(current_credentials['username'], current_credentials['password']),
            verify=False,
            timeout=10
        )
        
        if response.status_code == 200:
            return jsonify({'success': True, 'message': 'Data submitted successfully'}), 200
        else:
            return jsonify({'success': False, 'message': f'Submission failed: {response.text}'}), response.status_code
    
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500

@app.route('/api/schedule', methods=['POST'])
def schedule_submission():
    """Schedule automatic data submission"""
    
    if not current_credentials['username'] or not current_credentials['password']:
        return jsonify({'success': False, 'message': 'Please login first'}), 401
    
    data = request.json
    interval_minutes = data.get('interval', 60)
    submission_data = data.get('data', {})
    
    def scheduled_task():
        try:
            requests.post(
                'https://elog.pedc.ir/api/submit',
                json=submission_data,
                auth=HTTPBasicAuth(current_credentials['username'], current_credentials['password']),
                verify=False,
                timeout=10
            )
        except Exception as e:
            print(f"Scheduled submission error: {str(e)}")
    
    try:
        # Remove existing scheduled job if present
        if scheduler.get_job('scheduled_submission'):
            scheduler.remove_job('scheduled_submission')
        
        # Add new job
        scheduler.add_job(
            scheduled_task,
            'interval',
            minutes=interval_minutes,
            id='scheduled_submission',
            replace_existing=True
        )
        
        return jsonify({'success': True, 'message': f'Scheduled every {interval_minutes} minutes'}), 200
    
    except Exception as e:
        return jsonify({'success': False, 'message': f'Scheduling error: {str(e)}'}), 500

@app.route('/api/stop-schedule', methods=['POST'])
def stop_schedule():
    """Stop scheduled submission"""
    try:
        if scheduler.get_job('scheduled_submission'):
            scheduler.remove_job('scheduled_submission')
            return jsonify({'success': True, 'message': 'Schedule stopped'}), 200
        return jsonify({'success': False, 'message': 'No active schedule'}), 400
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
