from flask import Flask, render_template, request, jsonify, session
from apscheduler.schedulers.background import BackgroundScheduler
import requests
from dotenv import load_dotenv
import os
from datetime import datetime

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'your-secret-key-here')

scheduler = BackgroundScheduler()
scheduler.start()

# ذخیره وضعیت هر کاربر
user_sessions = {}

TARGET_URL = 'https://elog.pedc.ir/api/submit'

def submit_data(username, password):
    """ارسال داده با اطلاعات کاربر"""
    try:
        payload = {
            'username': username,
            'password': password,
            'data': 'test_data'
        }
        
        response = requests.post(
            TARGET_URL,
            json=payload,
            verify=False,
            timeout=10
        )
        
        if response.status_code == 200:
            return {
                'success': True,
                'message': f'✅ ارسال موفق: {response.status_code}',
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        else:
            return {
                'success': False,
                'message': f'⚠️ خطا: {response.status_code}',
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
    except Exception as e:
        return {
            'success': False,
            'message': f'❌ خطا: {str(e)}',
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

@app.route('/')
def index():
    """صفحه ورود"""
    return render_template('index.html')

@app.route('/api/login', methods=['POST'])
def login():
    """ورود کاربر"""
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    
    if not username or not password:
        return jsonify({
            'success': False,
            'message': 'نام کاربری و رمز عبور الزامی است'
        }), 400
    
    # ذخیره در session
    session['username'] = username
    session['password'] = password
    session['logged_in'] = True
    
    return jsonify({
        'success': True,
        'message': f'خوش آمدید {username}!'
    })

@app.route('/api/dashboard')
def dashboard():
    """بررسی ورود"""
    if not session.get('logged_in'):
        return jsonify({
            'success': False,
            'message': 'ابتدا وارد شوید'
        }), 401
    
    username = session.get('username')
    
    # دریافت وضعیت کاربر
    user_data = user_sessions.get(username, {
        'enabled': False,
        'last_run': None,
        'interval': 60,
        'message': 'خودکارسازی غیرفعال است'
    })
    
    return jsonify({
        'success': True,
        'username': username,
        'status': user_data
    })

@app.route('/api/status', methods=['GET'])
def get_status():
    """دریافت وضعیت"""
    if not session.get('logged_in'):
        return jsonify({'success': False}), 401
    
    username = session.get('username')
    status = user_sessions.get(username, {
        'enabled': False,
        'last_run': None,
        'message': 'خودکارسازی غیرفعال است'
    })
    
    return jsonify(status)

@app.route('/api/submit', methods=['POST'])
def submit_manual():
    """ارسال دستی"""
    if not session.get('logged_in'):
        return jsonify({'success': False, 'message': 'ابتدا وارد شوید'}), 401
    
    username = session.get('username')
    password = session.get('password')
    
    result = submit_data(username, password)
    
    # ذخیره نتیجه
    if username not in user_sessions:
        user_sessions[username] = {}
    
    user_sessions[username]['last_run'] = result['timestamp']
    user_sessions[username]['message'] = result['message']
    
    return jsonify({
        'success': result['success'],
        'message': result['message'],
        'status': user_sessions[username]
    })

@app.route('/api/schedule', methods=['POST'])
def set_schedule():
    """تنظیم خودکارسازی"""
    if not session.get('logged_in'):
        return jsonify({'success': False}), 401
    
    data = request.get_json()
    username = session.get('username')
    password = session.get('password')
    interval = data.get('interval', 60)
    enabled = data.get('enabled', False)
    
    if username not in user_sessions:
        user_sessions[username] = {}
    
    user_sessions[username]['enabled'] = enabled
    user_sessions[username]['interval'] = interval
    
    if enabled:
        # حذف job قدیمی اگر وجود دارد
        job_id = f'job_{username}'
        try:
            scheduler.remove_job(job_id)
        except:
            pass
        
        # اضافه کردن job جدید
        def scheduled_submit():
            result = submit_data(username, password)
            user_sessions[username]['last_run'] = result['timestamp']
            user_sessions[username]['message'] = result['message']
        
        scheduler.add_job(
            scheduled_submit,
            'interval',
            minutes=interval,
            id=job_id
        )
        
        user_sessions[username]['message'] = f'✅ خودکار هر {interval} دقیقه'
    else:
        # حذف job
        job_id = f'job_{username}'
        try:
            scheduler.remove_job(job_id)
        except:
            pass
        
        user_sessions[username]['message'] = 'خودکارسازی غیرفعال است'
    
    return jsonify({
        'success': True,
        'status': user_sessions[username]
    })

@app.route('/api/test', methods=['POST'])
def test_connection():
    """تست اتصال"""
    if not session.get('logged_in'):
        return jsonify({'success': False}), 401
    
    username = session.get('username')
    password = session.get('password')
    
    try:
        # تست ورود
        payload = {
            'username': username,
            'password': password
        }
        
        response = requests.post(
            TARGET_URL,
            json=payload,
            verify=False,
            timeout=5
        )
        
        return jsonify({
            'success': True,
            'message': f'✅ اتصال موفق! (کد: {response.status_code})',
            'status_code': response.status_code
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'❌ خطا در اتصال: {str(e)}'
        }), 500

@app.route('/api/logout', methods=['POST'])
def logout():
    """خروج"""
    username = session.get('username')
    
    # حذف job
    if username:
        job_id = f'job_{username}'
        try:
            scheduler.remove_job(job_id)
        except:
            pass
    
    session.clear()
    
    return jsonify({'success': True, 'message': 'با موفقیت خارج شدید'})

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000)
