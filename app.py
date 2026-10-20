from flask import Flask, render_template, request, jsonify
import requests
import os
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler

load_dotenv()

app = Flask(__name__)
scheduler = BackgroundScheduler()
scheduler.start()

user_data = {
    'api_url': 'https://elog.pedc.ir/api/submit',
    'username': 'R.babaei',
    'password': 'R@46',
    'parameters': {},
    'description': '',
    'job_id': None
}

def submit_to_website():
    try:
        # ✅ پروکسی شما
        proxy_url = 'http://81.90.158.110:3128'
        
        proxies = {
            'http': proxy_url,
            'https': proxy_url
        }
        
        # ✅ درخواست ارسال کن
        payload = {
            'username': user_data[''],
            'password': user_data[''],
            'description': user_data['description'],
            **user_data.get('parameters', {})
        }
        
        headers = {'Content-Type': 'application/json'}
        
        response = requests.post(
            user_data['api_url'],
            json=payload,
            headers=headers,
            proxies=proxies,  # ✅ پروکسی استفاده شد
            timeout=15,
            verify=False  # SSL را نادیده بگیر
        )
        
        print(f"✅ موفق: {response.status_code}")
        print(response.json())
        
    except Exception as e:
        print(f"❌ خطا: {e}")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/config', methods=['POST'])
def save_config():
    global user_data
    data = request.json
    user_data['api_url'] = data.get('api_url', 'https://elog.pedc.ir/api/submit')
    user_data['username'] = data.get('username', 'R.babaei')
    user_data['password'] = data.get('password', 'R@46')
    user_data['description'] = data.get('description', '')
    user_data['parameters'] = data.get('parameters', {})
    return jsonify({'status': 'success', 'message': '✅ ذخیره شد'})

@app.route('/api/start', methods=['POST'])
def start_automation():
    global user_data
    if user_data['job_id']:
        return jsonify({'status': 'error', 'message': '⚠️ در حال اجرا'}), 400
    job = scheduler.add_job(submit_to_website, 'interval', hours=1)
    user_data['job_id'] = job.id
    submit_to_website()
    return jsonify({'status': 'success', 'message': '▶️ شروع شد'})

@app.route('/api/stop', methods=['POST'])
def stop_automation():
    global user_data
    if user_data['job_id']:
        scheduler.remove_job(user_data['job_id'])
        user_data['job_id'] = None
    return jsonify({'status': 'success', 'message': '⏹️ متوقف'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
