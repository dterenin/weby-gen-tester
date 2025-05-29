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
    deps_status = {}
    
    try:
        # Check Node.js
        node_result = subprocess.run(['node', '--version'], capture_output=True, text=True)
        if node_result.returncode == 0:
            deps_status['node'] = f"✓ Node.js: {node_result.stdout.strip()}"
        else:
            deps_status['node'] = "✗ Node.js not found"
            
        # Check pnpm
        pnpm_result = subprocess.run(['pnpm', '--version'], capture_output=True, text=True)
        if pnpm_result.returncode == 0:
            deps_status['pnpm'] = f"✓ pnpm: {pnpm_result.stdout.strip()}"
        else:
            deps_status['pnpm'] = "✗ pnpm not found"
            
        # Check Python
        deps_status['python'] = f"✓ Python: {sys.version.split()[0]}"
        
        # Check PATH
        deps_status['path'] = f"PATH: {os.environ.get('PATH', 'Not found')}"
        
        # Check which node
        which_result = subprocess.run(['which', 'node'], capture_output=True, text=True)
        if which_result.returncode == 0:
            deps_status['node_path'] = f"Node path: {which_result.stdout.strip()}"
        else:
            deps_status['node_path'] = "Node path: not found"
            
        return deps_status
        
    except Exception as e:
        deps_status['error'] = f"Error checking dependencies: {e}"
        return deps_status

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
        .output { background: #1f2937; color: #f9fafb; padding: 15px; border-radius: 5px; font-family: monospace; white-space: pre-wrap; max-height: 400px; overflow-y: auto; }
        .deps { background: #f3f4f6; padding: 10px; border-radius: 5px; font-family: monospace; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🧪 NextJS Web Tester - Debug Interface</h1>
            <p>Debug interface for dependency checking and test execution</p>
        </div>
        
        <div class="section">
            <h2>System Dependencies</h2>
            <div id="dependencies" class="deps">Loading...</div>
            <button class="button" onclick="checkDeps()">Refresh Dependencies</button>
        </div>
        
        <div class="section">
            <h2>Test Commands</h2>
            <button class="button" onclick="runTest('python3 --version')">Check Python</button>
            <button class="button" onclick="runTest('pytest --version')">Check Pytest</button>
            <button class="button" onclick="runTest('pytest test_nextjs_site.py -v --tb=short')">Run Tests</button>
        </div>
        
        <div class="section">
            <h2>Test Output</h2>
            <div id="output" class="output">No tests run yet...</div>
        </div>
    </div>
    
    <script>
        function checkDeps() {
            fetch('/dependencies')
            .then(response => response.json())
            .then(data => {
                let html = '';
                for (const [key, value] of Object.entries(data)) {
                    html += key + ': ' + value + '\n';
                }
                document.getElementById('dependencies').textContent = html;
            });
        }
        
        function runTest(command) {
            fetch('/run-test', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({command: command})
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    setTimeout(checkStatus, 1000);
                }
            });
        }
        
        function checkStatus() {
            fetch('/status')
            .then(response => response.json())
            .then(data => {
                if (data.output) {
                    document.getElementById('output').textContent = data.output;
                }
                if (data.running) {
                    setTimeout(checkStatus, 2000);
                }
            });
        }
        
        // Load dependencies on page load
        checkDeps();
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/dependencies')
def dependencies():
    return jsonify(check_dependencies())

@app.route('/run-test', methods=['POST'])
def run_test():
    global test_running
    
    if test_running:
        return jsonify({'success': False, 'message': 'Tests are already running'})
    
    data = request.get_json()
    command = data.get('command', 'python3 --version')
    
    # Start tests in background thread
    thread = threading.Thread(target=run_tests_async, args=(command,))
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
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()})

if __name__ == "__main__":
    # Setup signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    print("NextJS Web Tester is starting...")
    
    # Check dependencies but don't exit on failure
    deps = check_dependencies()
    print("\nDependency Status:")
    for key, value in deps.items():
        print(f"  {key}: {value}")
    
    print("\n🌐 Starting web interface...")
    print("\n📍 Access the debug interface at: http://localhost:5000")
    print("\n🚀 Ready for debugging!")
    
    # Start Flask app
    app.run(host='0.0.0.0', port=5000, debug=False)