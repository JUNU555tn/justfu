
from flask import Flask
import threading
import os

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

@app.route('/health')
def health():
    return {"status": "healthy", "bot": "running"}

def run_web_server():
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

def start_web_server():
    server_thread = threading.Thread(target=run_web_server)
    server_thread.daemon = True
    server_thread.start()
