from flask import Flask, render_template, request, jsonify
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from apscheduler.schedulers.background import BackgroundScheduler
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
import os

app = Flask(__name__)
scheduler = BackgroundScheduler()
scheduler.start()

user_data = {
    'site_url': '',
    'username': '',
    'password': '',
    'parameters': {},
    'description': '',
    'job_id': None
}

def submit_to_website():
    try:
        options = webdriver.ChromeOptions()
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--headless')
        
        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=options
        )
        
        driver.get(user_data['site_url'])
        wait = WebDriverWait(driver, 10)
        
        username_field = wait.until(EC.presence_of_element_located((By.NAME, 'username')))
        username_field.send_keys(user_data['username'])
        
        password_field = driver.find_element(By.NAME, 'password')
        password_field.send_keys(user_data['password'])
        
        login_btn = driver.find_element(By.ID, 'login_btn')
        login_btn.click()
        
        import time
        time.sleep(3)
        
        for name, value in user_data.get('parameters', {}).items():
            try:
                field = driver.find_element(By.NAME, name)
                field.clear()
                field.send_keys(str(value))
            except:
                pass
        
        try:
            text_field = driver.find_element(By.NAME, 'text_field')
            text_field.clear()
            text_field.send_keys(user_data['description'])
        except:
            pass
        
        submit_btn = driver.find_element(By.ID, 'submit_btn')
        submit_btn.click()
        
        driver.quit()
        print("✅ ارسال موفق")
        
    except Exception as e:
        print(f"❌ خطا: {e}")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/config', methods=['POST'])
def save_config():
    global user_data
    data = request.json
    
    user_data['site_url'] = data.get('https://elog.pedc.ir/DataHistory/IndexWell', '')
    user_data['username'] = data.get('username', 'R.babaei')
    user_data['password'] = data.get('password', 'R@46')
    user_data['description'] = data.get('description', '')
    user_data['parameters'] = data.get('parameters', {})
    
    return jsonify({'status': 'success', 'message': '✅ ذخیره شد'})

@app.route('/api/start', methods=['POST'])
def start_automation():
    global user_data
    
    if not user_data['site_url']:
        return jsonify({'status': 'error', 'message': '❌ تنظیمات ناقص'}), 400
    
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
