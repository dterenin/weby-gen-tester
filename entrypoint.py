#!/usr/bin/env python3
import subprocess
import time
import os
import signal
import sys
from pathlib import Path

def start_streamlit():
    """Start Streamlit server on port 8501"""
    print("🚀 Starting Streamlit on 0.0.0.0:8501...")
    return subprocess.Popen([
        "streamlit", "run", "main.py",
        "--server.address", "0.0.0.0",
        "--server.port", "8501",
        "--server.headless", "true",
        "--server.enableCORS", "false",
        "--server.enableXsrfProtection", "false"
    ])

def start_allure_server():
    """Start Allure server on port 8502"""
    allure_results = Path("/app/allure-results")
    
    if allure_results.exists() and any(allure_results.iterdir()):
        print("📊 Starting Allure server on 0.0.0.0:8502...")
        return subprocess.Popen([
            "allure", "serve", "/app/allure-results",
            "--port", "8502",
            "--host", "0.0.0.0"
        ])
    else:
        print("📊 Starting Allure placeholder on 0.0.0.0:8502...")
        return subprocess.Popen([
            "python3", "-c", """
import http.server
import socketserver

class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        html = '''<!DOCTYPE html>
<html><head><title>Allure Reports - Port 8502</title>
<style>body{font-family:Arial;text-align:center;margin:50px;background:#f5f5f5}
.container{max-width:600px;margin:0 auto;background:white;padding:40px;border-radius:10px;box-shadow:0 2px 10px rgba(0,0,0,0.1)}
.status{color:#666;margin:20px 0}</style></head>
<body><div class="container">
<h1>🧪 Allure Reports</h1>
<div class="status">Service running on port 8502</div>
<p>No test results available yet.</p>
<p>Run some tests to see reports here!</p>
<hr><small>Railway Magic Port: 8502</small>
</div></body></html>'''
        self.wfile.write(html.encode('utf-8'))

print('🌐 Allure placeholder server starting on 0.0.0.0:8502')
with socketserver.TCPServer(('0.0.0.0', 8502), Handler) as httpd:
    httpd.serve_forever()
"""
        ])

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    print(f"🛑 Received signal {signum}, shutting down...")
    sys.exit(0)

if __name__ == "__main__":
    # Set up signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    processes = []
    
    try:
        print("🚀 Starting multi-port Railway service...")
        
        # Start Streamlit (main service)
        streamlit_proc = start_streamlit()
        processes.append(streamlit_proc)
        
        # Wait for Streamlit to initialize
        time.sleep(3)
        
        # Start Allure server (secondary service)
        allure_proc = start_allure_server()
        processes.append(allure_proc)
        
        print("✅ All services started successfully!")
        print("📱 Streamlit: http://0.0.0.0:8501")
        print("📊 Allure: http://0.0.0.0:8502")
        print("🎯 Railway will auto-detect both ports for Magic Ports")
        
        # Keep the main process alive and monitor subprocesses
        while True:
            for proc in processes[:]:
                if proc.poll() is not None:
                    print(f"❌ Process {proc.pid} exited with code {proc.returncode}")
                    processes.remove(proc)
                    if not processes:
                        print("💥 All processes exited, shutting down...")
                        sys.exit(1)
            time.sleep(2)
            
    except KeyboardInterrupt:
        print("⏹️ Received interrupt signal, shutting down...")
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
    finally:
        # Clean up processes
        print("🧹 Cleaning up processes...")
        for proc in processes:
            try:
                proc.terminate()
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
            except Exception:
                pass