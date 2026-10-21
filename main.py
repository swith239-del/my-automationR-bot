from flask import Flask, render_template, request, jsonify
from requests.auth import HTTPBasicAuth
import requests
import os
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
import atexit
import urllib3
import json

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
    
    print(f"[LOGIN] Attempting login for user: {username}")
    
    if not username or not password:
        return jsonify({'success': False, 'message': 'Username and password required'}), 400
    
    # Test credentials by making a request to the target API
    try:
        print(f"[LOGIN] Sending test request to elog.pedc.ir...")
        response = requests.get(
            'https://elog.pedc.ir/api/submit',
            auth=HTTPBasicAuth(username, password),
            verify=False,
            timeout=10
        )
        
        print(f"[LOGIN] Response status: {response.status_code}")
        print(f"[LOGIN] Response headers: {response.headers}")
        print(f"[LOGIN] Response body: {response.text[:500]}")
        
        if response.status_code in [200, 401, 403]:
            current_credentials['username'] = username
            current_credentials['password'] = password
            print(f"[LOGIN] ✓ Login successful")
            return jsonify({'success': True, 'message': 'Login successful'}), 200
        else:
            return jsonify({'success': False, 'message': f'Authentication failed: {response.status_code}'}), 401
    
    except Exception as e:
        print(f"[LOGIN] ✗ Error: {str(e)}")
        return jsonify({'success': False, 'message': f'Connection error: {str(e)}'}), 500

@app.route('/api/submit', methods=['POST'])
def submit_data():
    """Submit data to elog.pedc.ir"""
    
    print(f"[SUBMIT] Request received")
    
    if not current_credentials['username'] or not current_credentials['password']:
        print(f"[SUBMIT] ✗ Not authenticated")
        return jsonify({'success': False, 'message': 'Please login first'}), 401
    
    data = request.json
    print(f"[SUBMIT] Data: {json.dumps(data, indent=2)}")
    
    try:
        print(f"[SUBMIT] Sending POST request to elog.pedc.ir...")
        response = requests.post(
            'https://elog.pedc.ir/api/submit',
            json=data,
            auth=HTTPBasicAuth(current_credentials['username'], current_credentials['password']),
            verify=False,
            timeout=10
        )
        
        print(f"[SUBMIT] Status: {response.status_code}")
        print(f"[SUBMIT] Headers: {response.headers}")
        print(f"[SUBMIT] Body: {response.text[:500]}")
        
        if response.status_code == 200:
            print(f"[SUBMIT] ✓ Success")
            return jsonify({'success': True, 'message': 'Data submitted successfully'}), 200
        else:
            print(f"[SUBMIT] ✗ Failed with status {response.status_code}")
            return jsonify({'success': False, 'message': f'Submission failed: {response.text}'}), response.status_code
    
    except Exception as e:
        print(f"[SUBMIT] ✗ Exception: {str(e)}")
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500

@app.route('/api/schedule', methods=['POST'])
def schedule_submission():
    """Schedule automatic data submission"""
    
    if not current_credentials['username'] or not current_credentials['password']:
        return jsonify({'success': False, 'message': 'Please login first'}), 401
    
    data = request.json
    interval_minutes = data.get('interval', 60)
    submission_data = data.get('data', {})
    
    print(f"[SCHEDULE] New schedule: every {interval_minutes} minutes")
    print(f"[SCHEDULE] Data: {json.dumps(submission_data, indent=2)}")
    
    def scheduled_task():
        try:
            print(f"[SCHEDULED_TASK] Executing...")
            requests.post(
                'https://elog.pedc.ir/api/submit',
                json=submission_data,
                auth=HTTPBasicAuth(current_credentials['username'], current_credentials['password']),
                verify=False,
                timeout=10
            )
            print(f"[SCHEDULED_TASK] ✓ Completed")
        except Exception as e:
            print(f"[SCHEDULED_TASK] ✗ Error: {str(e)}")
    
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
        print(f"[SCHEDULE] ✗ Error: {str(e)}")
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

@app.route('/api/test', methods=['GET'])
def test_endpoint():
    """Test endpoint for debugging"""
    return jsonify({
        'status': 'ok',
        'authenticated': bool(current_credentials['username']),
        'username': current_credentials['username'] or 'Not logged in'
    }), 200

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
