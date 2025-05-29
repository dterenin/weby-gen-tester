#!/usr/bin/env python3
import subprocess
import time
import os
import signal
import sys
from pathlib import Path
import threading
import http.server
import socketserver

def start_streamlit():
    """Start Streamlit server"""
    print("Starting Streamlit on port 8501...")
    return subprocess.Popen([
        "streamlit", "run", "main.py",
        "--server.address", "0.0.0.0",
        "--server.port", "8501"
    ])

def start_placeholder_server():
    """Start placeholder HTTP server"""
    class PlaceholderHandler(http.server.SimpleHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            html = """
            <!DOCTYPE html>
            <html>
            <head>
                <title>Allure Reports</title>
                <style>
                    body { font-family: Arial, sans-serif; margin: 40px; }
                    .container { max-width: 600px; margin: 0 auto; text-align: center; }
                    .status { color: #666; }
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>🧪 Allure Reports</h1>
                    <p class="status">No test results available yet.</p>
                    <p>Run some tests first to see the reports here!</p>
                    <hr>
                    <small>This service is running on port 8502</small>
                </div>
            </body>
            </html>
            """
            self.wfile.write(html.encode('utf-8'))
    
    def run_server():
        with socketserver.TCPServer(('0.0.0.0', 8502), PlaceholderHandler) as httpd:
            print("Placeholder server running on port 8502...")
            httpd.serve_forever()
    
    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()
    return thread

def start_allure_server():
    """Start Allure server if results exist, otherwise placeholder"""
    allure_results = Path("/app/allure-results")
    
    if allure_results.exists() and any(allure_results.iterdir()):
        print("Starting Allure server on port 8502...")
        return subprocess.Popen([
            "allure", "serve", "/app/allure-results",
            "--port", "8502",
            "--host", "0.0.0.0"
        ])
    else:
        print("No Allure results found, starting placeholder server...")
        start_placeholder_server()
        return None

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    print(f"Received signal {signum}, shutting down...")
    sys.exit(0)

if __name__ == "__main__":
    # Set up signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    processes = []
    
    try:
        # Start Streamlit
        streamlit_process = start_streamlit()
        processes.append(streamlit_process)
        
        # Wait a bit for Streamlit to initialize
        time.sleep(3)
        
        # Start Allure server or placeholder
        allure_process = start_allure_server()
        if allure_process:
            processes.append(allure_process)
        
        print("All services started successfully!")
        print("Streamlit: http://localhost:8501")
        print("Allure: http://localhost:8502")
        
        # Keep the main process alive and monitor subprocesses
        while True:
            for process in processes[:]:
                if process.poll() is not None:
                    print(f"Process {process.pid} exited with code {process.returncode}")
                    processes.remove(process)
                    if not processes:
                        print("All processes exited, shutting down...")
                        sys.exit(1)
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("Received interrupt signal, shutting down...")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
    finally:
        # Clean up processes
        for process in processes:
            try:
                process.terminate()
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
            except Exception:
                pass