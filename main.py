from flask import Flask, render_template, request, jsonify
from requests.auth import HTTPBasicAuth
import requests
import os
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
import atexit
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'your-secret-key-here')

current_credentials = {
    'username': None,
    'password': None
}

scheduler = BackgroundScheduler()
scheduler.start()
atexit.register(lambda: scheduler.shutdown())

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy'}), 200

@app.route('/')
def dashboard():
    print("[ROUTE] GET / - Serving dashboard")
    try:
        return render_template('index.html')
    except Exception as e:
        print(f"[ERROR] Template error: {e}")
        return f"Error: {e}", 500

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    print(f"[LOGIN] User: {username}")
    
    if not username or not password:
        return jsonify({'success': False, 'message': 'Username and password required'}), 400
    
    try:
        print(f"[LOGIN] Testing credentials...")
        response = requests.get(
            'https://elog.pedc.ir/',
            auth=HTTPBasicAuth(username, password),
            verify=False,
            timeout=10
        )
        
        print(f"[LOGIN] Status: {response.status_code}")
        
        if response.status_code in [200, 302, 401, 403]:
            current_credentials['username'] = username
            current_credentials['password'] = password
            print(f"[LOGIN] ✓ Success")
            return jsonify({'success': True, 'message': 'Login successful'}), 200
        else:
            return jsonify({'success': False, 'message': f'Failed: {response.status_code}'}), 401
    
    except Exception as e:
        print(f"[LOGIN] ✗ Error: {str(e)}")
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500

@app.route('/api/submit', methods=['POST'])
def submit_data():
    if not current_credentials['username']:
        return jsonify({'success': False, 'message': 'Please login first'}), 401
    
    data = request.json
    print(f"[SUBMIT] Data: {data}")
    
    try:
        response = requests.post(
            'https://elog.pedc.ir/api/submit',
            json=data,
            auth=HTTPBasicAuth(current_credentials['username'], current_credentials['password']),
            verify=False,
            timeout=10
        )
        
        print(f"[SUBMIT] Status: {response.status_code}")
        
        if response.status_code in [200, 201]:
            return jsonify({'success': True, 'message': 'Submitted successfully'}), 200
        else:
            return jsonify({'success': False, 'message': f'Failed: {response.status_code}'}), response.status_code
    
    except Exception as e:
        print(f"[SUBMIT] ✗ Error: {str(e)}")
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500

@app.route('/api/schedule', methods=['POST'])
def schedule_submission():
    if not current_credentials['username']:
        return jsonify({'success': False, 'message': 'Please login first'}), 401
    
    data = request.json
    interval_minutes = data.get('interval', 60)
    submission_data = data.get('data', {})
    
    def scheduled_task():
        try:
            print(f"[TASK] Running...")
            requests.post(
                'https://elog.pedc.ir/api/submit',
                json=submission_data,
                auth=HTTPBasicAuth(current_credentials['username'], current_credentials['password']),
                verify=False,
                timeout=10
            )
            print(f"[TASK] ✓ Done")
        except Exception as e:
            print(f"[TASK] ✗ Error: {str(e)}")
    
    try:
        if scheduler.get_job('scheduled_submission'):
            scheduler.remove_job('scheduled_submission')
        
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
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500

@app.route('/api/stop-schedule', methods=['POST'])
def stop_schedule():
    try:
        if scheduler.get_job('scheduled_submission'):
            scheduler.remove_job('scheduled_submission')
            return jsonify({'success': True, 'message': 'Stopped'}), 200
        return jsonify({'success': False, 'message': 'No schedule'}), 400
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    print(f"[START] Running on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
