import subprocess
import sys
import os
import signal
import time
from flask import Flask, render_template_string, request, jsonify
import threading
import json
from datetime import datetime

app = Flask(__name__)

# Global variables for test status
test_running = False
test_results = {}
last_test_output = ""

def signal_handler(sig, frame):
    print('\nShutting down NextJS Web Tester...')
    sys.exit(0)

def check_dependencies():
    """Check if required dependencies are available"""
    try:
        # Check Node.js
        node_result = subprocess.run(['node', '--version'], capture_output=True, text=True)
        if node_result.returncode == 0:
            print(f"✓ Node.js: {node_result.stdout.strip()}")
        else:
            print("✗ Node.js not found")
            return False
            
        # Check pnpm
        pnpm_result = subprocess.run(['pnpm', '--version'], capture_output=True, text=True)
        if pnpm_result.returncode == 0:
            print(f"✓ pnpm: {pnpm_result.stdout.strip()}")
        else:
            print("✗ pnpm not found")
            return False
            
        # Check Python
        print(f"✓ Python: {sys.version.split()[0]}")
        
        return True
    except Exception as e:
        print(f"Error checking dependencies: {e}")
        return False

def run_tests_async(test_command):
    """Run tests in background thread"""
    global test_running, last_test_output, test_results
    
    test_running = True
    try:
        result = subprocess.run(
            test_command, 
            capture_output=True, 
            text=True, 
            shell=True
        )
        
        last_test_output = f"STDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}"
        test_results = {
            'returncode': result.returncode,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'timestamp': datetime.now().isoformat(),
            'command': test_command
        }
    except Exception as e:
        last_test_output = f"Error running tests: {str(e)}"
        test_results = {
            'error': str(e),
            'timestamp': datetime.now().isoformat(),
            'command': test_command
        }
    finally:
        test_running = False

# HTML template for the web interface
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
        .status { padding: 10px; border-radius: 5px; margin: 10px 0; }
        .status.running { background: #fef3c7; color: #92400e; }
        .status.success { background: #d1fae5; color: #065f46; }
        .status.error { background: #fee2e2; color: #991b1b; }
        .input-group { margin: 10px 0; }
        .input-group label { display: block; margin-bottom: 5px; font-weight: bold; }
        .input-group input { width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🧪 NextJS Web Tester - Debug Interface</h1>
            <p>Simple web interface for running and debugging tests</p>
        </div>
        
        <div class="section">
            <h2>Quick Test Commands</h2>
            <button class="button" onclick="runTest('pytest test_nextjs_site.py -v')">Run Basic Tests</button>
            <button class="button" onclick="runTest('pytest test_nextjs_site.py -v -s')">Run Tests (Verbose)</button>
            <button class="button" onclick="runTest('pytest test_nextjs_site.py --alluredir=allure-results')">Run with Allure</button>
            <button class="button" onclick="checkStatus()">Check Status</button>
        </div>
        
        <div class="section">
            <h2>Custom Command</h2>
            <div class="input-group">
                <label for="customCommand">Enter custom pytest command:</label>
                <input type="text" id="customCommand" placeholder="pytest test_nextjs_site.py --your-options" value="pytest test_nextjs_site.py -v">
                <button class="button" onclick="runCustomTest()">Run Custom Command</button>
            </div>
        </div>
        
        <div class="section">
            <h2>Test Status</h2>
            <div id="status" class="status">Ready to run tests</div>
        </div>
        
        <div class="section">
            <h2>Test Output</h2>
            <div id="output" class="output">No tests run yet...</div>
        </div>
    </div>
    
    <script>
        let statusCheckInterval;
        
        function runTest(command) {
            fetch('/run-test', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({command: command})
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    document.getElementById('status').innerHTML = 'Tests started...';
                    document.getElementById('status').className = 'status running';
                    startStatusCheck();
                } else {
                    document.getElementById('status').innerHTML = 'Error: ' + data.message;
                    document.getElementById('status').className = 'status error';
                }
            })
            .catch(error => {
                document.getElementById('status').innerHTML = 'Network error: ' + error;
                document.getElementById('status').className = 'status error';
            });
        }
        
        function runCustomTest() {
            const command = document.getElementById('customCommand').value;
            if (command.trim()) {
                runTest(command);
            }
        }
        
        function checkStatus() {
            fetch('/status')
            .then(response => response.json())
            .then(data => {
                const statusDiv = document.getElementById('status');
                const outputDiv = document.getElementById('output');
                
                if (data.running) {
                    statusDiv.innerHTML = 'Tests are running...';
                    statusDiv.className = 'status running';
                } else {
                    if (data.results && data.results.returncode !== undefined) {
                        if (data.results.returncode === 0) {
                            statusDiv.innerHTML = 'Tests completed successfully!';
                            statusDiv.className = 'status success';
                        } else {
                            statusDiv.innerHTML = 'Tests failed (exit code: ' + data.results.returncode + ')';
                            statusDiv.className = 'status error';
                        }
                    } else {
                        statusDiv.innerHTML = 'Ready to run tests';
                        statusDiv.className = 'status';
                    }
                }
                
                if (data.output) {
                    outputDiv.textContent = data.output;
                    outputDiv.scrollTop = outputDiv.scrollHeight;
                }
                
                if (!data.running && statusCheckInterval) {
                    clearInterval(statusCheckInterval);
                    statusCheckInterval = null;
                }
            })
            .catch(error => {
                console.error('Status check error:', error);
            });
        }
        
        function startStatusCheck() {
            if (statusCheckInterval) clearInterval(statusCheckInterval);
            statusCheckInterval = setInterval(checkStatus, 2000);
        }
        
        // Check status on page load
        checkStatus();
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/run-test', methods=['POST'])
def run_test():
    global test_running
    
    if test_running:
        return jsonify({'success': False, 'message': 'Tests are already running'})
    
    data = request.get_json()
    command = data.get('command', 'pytest test_nextjs_site.py -v')
    
    # Start tests in background thread
    thread = threading.Thread(target=run_tests_async, args=(command,))
    thread.daemon = True
    thread.start()
    
    return jsonify({'success': True, 'message': 'Tests started'})

@app.route('/status')
def status():
    return jsonify({
        'running': test_running,
        'output': last_test_output,
        'results': test_results
    })

@app.route('/health')
def health():
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

if __name__ == "__main__":
    # Setup signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    print("NextJS Web Tester is starting...")
    
    if check_dependencies():
        print("\n✓ All dependencies are available!")
        print("\n🌐 Starting web interface...")
        print("\n📍 Access the debug interface at: http://localhost:5000")
        print("\n🔧 Available endpoints:")
        print("  • / - Main debug interface")
        print("  • /status - Test status API")
        print("  • /health - Health check")
        print("\n🚀 Ready for testing!")
        
        # Start Flask app
        app.run(host='0.0.0.0', port=5000, debug=False)
    else:
        print("\n✗ Missing dependencies. Please install Node.js and pnpm.")
        sys.exit(1)