import subprocess
import sys
import os
import signal
from flask import Flask, render_template_string, request, jsonify
import threading
from datetime import datetime

app = Flask(__name__)

# Global variables for test status
test_running = False
test_results = {}
last_test_output = ""

def signal_handler(sig, frame):
    print('\nShutting down NextJS Web Tester...')
    sys.exit(0)

def run_command_async(command):
    """Run command in background thread"""
    global test_running, last_test_output, test_results
    
    test_running = True
    try:
        result = subprocess.run(
            command, 
            capture_output=True, 
            text=True, 
            shell=True
        )
        
        last_test_output = f"Command: {command}\n\nSTDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}\n\nReturn code: {result.returncode}"
        test_results = {
            'returncode': result.returncode,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'timestamp': datetime.now().isoformat(),
            'command': command
        }
    except Exception as e:
        last_test_output = f"Error running command '{command}': {str(e)}"
        test_results = {
            'error': str(e),
            'timestamp': datetime.now().isoformat(),
            'command': command
        }
    finally:
        test_running = False

# Simple HTML template for debugging
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>NextJS Web Tester - Debug Interface</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; }
        .header { background: #2563eb; color: white; padding: 15px; border-radius: 5px; margin-bottom: 20px; }
        .section { margin: 20px 0; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }
        .button { background: #2563eb; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; margin: 5px; }
        .button:hover { background: #1d4ed8; }
        .button:disabled { background: #9ca3af; cursor: not-allowed; }
        .output { background: #1f2937; color: #f9fafb; padding: 15px; border-radius: 5px; font-family: monospace; white-space: pre-wrap; max-height: 400px; overflow-y: auto; }
        .input-group { margin: 10px 0; }
        .input-group input { width: 70%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; }
        .status { padding: 10px; border-radius: 5px; margin: 10px 0; background: #f3f4f6; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🧪 NextJS Web Tester - Debug Interface</h1>
            <p>Simple debug interface - Node.js dependency check bypassed</p>
        </div>
        
        <div class="section">
            <h2>System Check Commands</h2>
            <button class="button" onclick="runCommand('python3 --version')">Check Python</button>
            <button class="button" onclick="runCommand('which python3')">Python Path</button>
            <button class="button" onclick="runCommand('ls -la /usr/local/bin/ | grep node')">Find Node</button>
            <button class="button" onclick="runCommand('echo $PATH')">Check PATH</button>
            <button class="button" onclick="runCommand('whoami')">Current User</button>
            <button class="button" onclick="runCommand('pwd')">Current Directory</button>
        </div>
        
        <div class="section">
            <h2>Test Commands</h2>
            <button class="button" onclick="runCommand('pytest --version')">Check Pytest</button>
            <button class="button" onclick="runCommand('ls -la')">List Files</button>
            <button class="button" onclick="runCommand('python3 -c \"import playwright; print(\\\"Playwright OK\\\")\\\"\')">Check Playwright</button>
            <button class="button" onclick="runCommand('pytest test_nextjs_site.py --collect-only')">Collect Tests</button>
        </div>
        
        <div class="section">
            <h2>Custom Command</h2>
            <div class="input-group">
                <input type="text" id="customCommand" placeholder="Enter any shell command" value="ls -la">
                <button class="button" onclick="runCustomCommand()">Run Command</button>
            </div>
        </div>
        
        <div class="section">
            <h2>Status</h2>
            <div id="status" class="status">Ready</div>
        </div>
        
        <div class="section">
            <h2>Command Output</h2>
            <div id="output" class="output">No commands run yet...</div>
        </div>
    </div>
    
    <script>
        function runCommand(command) {
            document.getElementById('status').textContent = 'Running: ' + command;
            
            fetch('/run-command', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({command: command})
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    setTimeout(checkStatus, 500);
                } else {
                    document.getElementById('status').textContent = 'Error: ' + data.message;
                }
            })
            .catch(error => {
                document.getElementById('status').textContent = 'Network error: ' + error;
            });
        }
        
        function runCustomCommand() {
            const command = document.getElementById('customCommand').value;
            if (command.trim()) {
                runCommand(command);
            }
        }
        
        function checkStatus() {
            fetch('/status')
            .then(response => response.json())
            .then(data => {
                if (data.running) {
                    document.getElementById('status').textContent = 'Command running...';
                    setTimeout(checkStatus, 1000);
                } else {
                    document.getElementById('status').textContent = 'Ready';
                    if (data.output) {
                        document.getElementById('output').textContent = data.output;
                        document.getElementById('output').scrollTop = document.getElementById('output').scrollHeight;
                    }
                }
            })
            .catch(error => {
                console.error('Status check error:', error);
            });
        }
        
        // Allow Enter key in input field
        document.addEventListener('DOMContentLoaded', function() {
            document.getElementById('customCommand').addEventListener('keypress', function(e) {
                if (e.key === 'Enter') {
                    runCustomCommand();
                }
            });
        });
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/run-command', methods=['POST'])
def run_command():
    global test_running
    
    if test_running:
        return jsonify({'success': False, 'message': 'Another command is already running'})
    
    data = request.get_json()
    command = data.get('command', 'echo "No command specified"')
    
    # Start command in background thread
    thread = threading.Thread(target=run_command_async, args=(command,))
    thread.daemon = True
    thread.start()
    
    return jsonify({'success': True, 'message': 'Command started'})

@app.route('/status')
def status():
    return jsonify({
        'running': test_running,
        'output': last_test_output,
        'results': test_results
    })

@app.route('/health')
def health():
    return jsonify({
        'status': 'healthy', 
        'timestamp': datetime.now().isoformat(),
        'python_version': sys.version,
        'working_directory': os.getcwd()
    })

if __name__ == "__main__":
    # Setup signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    print("🚀 NextJS Web Tester - Debug Mode")
    print("📍 Starting web interface at: http://localhost:5000")
    print("🔧 Dependency checks bypassed - ready for debugging!")
    print(f"📂 Working directory: {os.getcwd()}")
    print(f"🐍 Python version: {sys.version.split()[0]}")
    
    # Start Flask app
    try:
        app.run(host='0.0.0.0', port=5000, debug=False)
    except Exception as e:
        print(f"❌ Failed to start web server: {e}")
        sys.exit(1)