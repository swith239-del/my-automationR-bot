import os
from flask import Flask, render_template, request, jsonify, session
from datetime import datetime
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from functools import wraps
from apscheduler.schedulers.background import BackgroundScheduler
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'your-secret-key-here-change-in-production')

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Global scheduler
scheduler = BackgroundScheduler()
scheduler.start()
active_jobs = {}

# Proxy configuration
PROXY_CONFIG = {
    'type': 'socks5',
    'ip': '22.212.197.248',
    'port': 12334,
    'auth': None
}

TARGET_URL = 'https://elog.pedc.ir/api/submit'

def get_session_with_retry():
    """Create requests session with retry strategy"""
    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS", "POST"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session

def get_proxy_url():
    """Build proxy URL from config"""
    proxy_type = PROXY_CONFIG['type']
    ip = PROXY_CONFIG['ip']
    port = PROXY_CONFIG['port']
    
    if PROXY_CONFIG['auth']:
        return f"{proxy_type}://{PROXY_CONFIG['auth']}@{ip}:{port}"
    return f"{proxy_type}://{ip}:{port}"

def require_login(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return jsonify({'error': 'Not authenticated'}), 401
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    """Serve main dashboard"""
    try:
        return render_template('index.html')
    except Exception as e:
        logger.error(f"Error serving index.html: {e}")
        return f"<h1>Error</h1><p>Cannot load dashboard: {str(e)}</p>", 500

@app.route('/api/login', methods=['POST'])
def api_login():
    """Login endpoint"""
    try:
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        
        if not username or not password:
            return jsonify({'success': False, 'message': 'Invalid credentials'}), 400
        
        # Store in session
        session['user'] = {
            'username': username,
            'password': password,
            'login_time': datetime.now().isoformat()
        }
        
        logger.info(f"User {username} logged in")
        return jsonify({'success': True, 'message': 'Logged in successfully'})
    
    except Exception as e:
        logger.error(f"Login error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/submit', methods=['POST'])
@require_login
def api_submit():
    """Submit data to ELOG"""
    try:
        data = request.get_json()
        username = session['user']['username']
        password = session['user']['password']
        
        # Prepare payload
        payload = {
            'username': username,
            'password': password,
            'data': data
        }
        
        # Get session with retry
        req_session = get_session_with_retry()
        
        # Use proxy
        proxy_url = get_proxy_url()
        proxies = {'http': proxy_url, 'https': proxy_url}
        
        # Make request
        response = req_session.post(
            TARGET_URL,
            json=payload,
            proxies=proxies,
            verify=False,
            timeout=10
        )
        
        logger.info(f"Submission response: {response.status_code}")
        
        if response.status_code == 200:
            return jsonify({'success': True, 'message': 'Data submitted successfully'})
        else:
            return jsonify({'success': False, 'message': f'Server error: {response.status_code}'}), response.status_code
    
    except Exception as e:
        logger.error(f"Submission error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/test-connection', methods=['GET'])
@require_login
def test_connection():
    """Test connection to ELOG"""
    try:
        req_session = get_session_with_retry()
        proxy_url = get_proxy_url()
        proxies = {'http': proxy_url, 'https': proxy_url}
        
        response = req_session.get(
            'https://elog.pedc.ir',
            proxies=proxies,
            verify=False,
            timeout=10
        )
        
        if response.status_code == 200:
            return jsonify({
                'success': True,
                'connected': True,
                'status': 'Connected',
                'timestamp': datetime.now().isoformat()
            })
        else:
            return jsonify({
                'success': True,
                'connected': False,
                'status': f'HTTP {response.status_code}',
                'timestamp': datetime.now().isoformat()
            })
    
    except Exception as e:
        logger.error(f"Connection test error: {e}")
        return jsonify({
            'success': False,
            'connected': False,
            'status': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/schedule/start', methods=['POST'])
@require_login
def start_schedule():
    """Start scheduled submissions"""
    try:
        data = request.get_json()
        interval = int(data.get('interval', 60))
        submit_data = data.get('data', {})
        job_id = f"job_{datetime.now().timestamp()}"
        
        def scheduled_task():
            # Create a request context
            with app.app_context():
                try:
                    req_session = get_session_with_retry()
                    proxy_url = get_proxy_url()
                    proxies = {'http': proxy_url, 'https': proxy_url}
                    
                    payload = {
                        'username': session['user']['username'],
                        'password': session['user']['password'],
                        'data': submit_data
                    }
                    
                    req_session.post(
                        TARGET_URL,
                        json=payload,
                        proxies=proxies,
                        verify=False,
                        timeout=10
                    )
                    logger.info(f"Scheduled task executed: {job_id}")
                except Exception as e:
                    logger.error(f"Scheduled task error: {e}")
        
        # Schedule job
        scheduler.add_job(
            scheduled_task,
            'interval',
            minutes=interval,
            id=job_id
        )
        
        active_jobs[job_id] = {
            'interval': interval,
            'started': datetime.now().isoformat(),
            'data': submit_data
        }
        
        return jsonify({'success': True, 'job_id': job_id, 'message': 'Schedule started'})
    
    except Exception as e:
        logger.error(f"Schedule start error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/schedule/stop/<job_id>', methods=['POST'])
@require_login
def stop_schedule(job_id):
    """Stop scheduled submission"""
    try:
        scheduler.remove_job(job_id)
        if job_id in active_jobs:
            del active_jobs[job_id]
        
        return jsonify({'success': True, 'message': 'Schedule stopped'})
    
    except Exception as e:
        logger.error(f"Schedule stop error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/schedule/list', methods=['GET'])
@require_login
def list_schedules():
    """List active schedules"""
    return jsonify({'jobs': active_jobs})

@app.route('/api/proxy/update', methods=['POST'])
@require_login
def update_proxy():
    """Update proxy configuration"""
    try:
        data = request.get_json()
        
        PROXY_CONFIG['type'] = data.get('type', 'socks5')
        PROXY_CONFIG['ip'] = data.get('ip', '22.212.197.248')
        PROXY_CONFIG['port'] = int(data.get('port', 12334))
        PROXY_CONFIG['auth'] = data.get('auth', None)
        
        logger.info(f"Proxy config updated")
        return jsonify({'success': True, 'message': 'Proxy configuration updated'})
    
    except Exception as e:
        logger.error(f"Proxy update error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/logout', methods=['POST'])
def logout():
    """Logout user"""
    session.clear()
    return jsonify({'success': True, 'message': 'Logged out'})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
