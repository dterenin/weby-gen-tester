import streamlit as st
import subprocess
import sys
import os
import threading
import time
from datetime import datetime
import json
import queue
from pathlib import Path
from streamlit_autorefresh import st_autorefresh
import shlex
import logging

# Configure Streamlit page
st.set_page_config(
    page_title="weby-gen-tester",
    page_icon="🧪",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
if 'test_running' not in st.session_state:
    st.session_state.test_running = False
if 'last_output' not in st.session_state:
    st.session_state.last_output = "No commands run yet..."
if 'test_results' not in st.session_state:
    st.session_state.test_results = {}
if 'command_history' not in st.session_state:
    st.session_state.command_history = []
if 'live_output' not in st.session_state:
    st.session_state.live_output = ""
if 'output_queue' not in st.session_state:
    st.session_state.output_queue = queue.Queue()
if 'current_process' not in st.session_state:
    st.session_state.current_process = None

def stream_output(process, output_queue):
    """Stream output from process to queue"""
    try:
        for line in iter(process.stdout.readline, ''):
            if line:
                output_queue.put(('stdout', line))
        for line in iter(process.stderr.readline, ''):
            if line:
                output_queue.put(('stderr', line))
    except Exception as e:
        output_queue.put(('error', str(e)))
    finally:
        output_queue.put(('done', process.returncode))

def validate_command(command):
    """Validate and sanitize command input"""
    # Whitelist of allowed commands
    allowed_commands = [
        'ls', 'cat', 'grep', 'find', 'python', 'pytest', 'allure', 
        'npm', 'node', 'git', 'docker', 'pip'
    ]
    
    # Parse command safely
    try:
        parts = shlex.split(command)
        if not parts:
            return False, "Empty command"
        
        base_command = parts[0]
        if base_command not in allowed_commands:
            return False, f"Command '{base_command}' not allowed"
        
        # Additional validation for dangerous patterns
        dangerous_patterns = ['&&', '||', ';', '|', '>', '<', '`', '$(']
        for pattern in dangerous_patterns:
            if pattern in command:
                return False, f"Dangerous pattern '{pattern}' detected"
        
        return True, "Command validated"
    except ValueError as e:
        return False, f"Invalid command syntax: {e}"

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('streamlit_audit.log'),
        logging.StreamHandler()
    ]
)

def run_command_async(command):
    # Log all command executions
    logging.info(f"Command executed: {command}")
    """Run command asynchronously with validation"""
    # Validate command first
    is_valid, message = validate_command(command)
    if not is_valid:
        return False, f"Security validation failed: {message}"
    
    try:
        st.session_state.test_running = True
        st.session_state.live_output = f"Starting command: {command}\n"
        
        # Use shlex.split for safer command parsing
        cmd_parts = shlex.split(command)
        
        # Start process WITHOUT shell=True for better security
        process = subprocess.Popen(
            cmd_parts,  # Use list instead of string
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            # shell=False  # Remove shell=True
            bufsize=1,
            universal_newlines=True
        )
        
        st.session_state.current_process = process
        
        # Start output streaming thread
        output_thread = threading.Thread(
            target=stream_output, 
            args=(process, st.session_state.output_queue)
        )
        output_thread.daemon = True
        output_thread.start()
        
        return True, "Command started successfully"
        
    except Exception as e:
        error_msg = f"Error starting command '{command}': {str(e)}"
        st.session_state.live_output = error_msg
        st.session_state.test_running = False
        return False, error_msg

def update_live_output():
    """Update live output from queue"""
    updated = False
    while not st.session_state.output_queue.empty():
        try:
            msg_type, content = st.session_state.output_queue.get_nowait()
            
            if msg_type == 'stdout':
                st.session_state.live_output += content
                updated = True
            elif msg_type == 'stderr':
                st.session_state.live_output += f"[STDERR] {content}"
                updated = True
            elif msg_type == 'error':
                st.session_state.live_output += f"[ERROR] {content}\n"
                updated = True
            elif msg_type == 'done':
                returncode = content
                st.session_state.live_output += f"\n[COMPLETED] Return code: {returncode}\n"
                st.session_state.test_running = False
                
                # Update history
                if st.session_state.command_history:
                    st.session_state.command_history[-1]['status'] = 'completed'
                    st.session_state.command_history[-1]['returncode'] = returncode
                
                # Update results
                st.session_state.test_results = {
                    'returncode': returncode,
                    'output': st.session_state.live_output,
                    'timestamp': datetime.now().isoformat()
                }
                
                st.session_state.last_output = st.session_state.live_output
                st.session_state.current_process = None
                updated = True
                
        except queue.Empty:
            break
    
    return updated

def stop_current_command():
    """Improved process termination"""
    if st.session_state.current_process:
        try:
            # Try graceful termination first
            st.session_state.current_process.terminate()
            
            # Wait for process to terminate
            try:
                st.session_state.current_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                # Force kill if graceful termination fails
                st.session_state.current_process.kill()
                st.session_state.current_process.wait()
            
            st.session_state.live_output += "\n[STOPPED] Command terminated by user\n"
            st.session_state.test_running = False
            st.session_state.current_process = None
            
        except Exception as e:
            st.session_state.live_output += f"\n[ERROR] Failed to stop command: {str(e)}\n"

# Sidebar with system info
with st.sidebar:
    st.header("📊 System Info")
    st.info(f"**Working Dir:** {os.getcwd()}")
    st.info(f"**Phoenix Traces:** [View Traces](https://arize-phoenix-production-a0af.up.railway.app/projects/UHJvamVjdDox/traces)")
    st.info(f"**Service Deployment:** [Restart Service](https://railway.com/project/d0a9c47a-4057-4091-b7c8-b7b175b5535d/service/281fa7de-4b73-4b81-b920-7d6b7ceb0d29?environmentId=6b0b0aa3-4d15-4569-998f-3f059c2240c1)")
    st.info(f"**Service Source:** [GitHub](https://github.com/dterenin/weby-gen-tester/tree/railway)")
    if st.button("🔄 Refresh"):
        st.rerun()
    
    # Command history
    st.header("📜 Command History")
    if st.session_state.command_history:
        for i, cmd in enumerate(reversed(st.session_state.command_history[-5:])):
            status_emoji = {
                'running': '🔄',
                'completed': '✅' if cmd.get('returncode', 0) == 0 else '✅',
                'error': '💥',
                'stopped': '⏹️'
            }.get(cmd['status'], '❓')
            
            st.text(f"✅  {cmd['command'][:30]}...")
    else:
        st.text("No commands yet")

# Custom command section
st.header("💻 Custom Command")

# Use form to enable Enter key submission
with st.form(key="command_form", clear_on_submit=False):
    col1, col2 = st.columns([4, 1])
    
    with col1:
        custom_command = st.text_input(
            "Enter any shell command:", 
            value="ls -la",
            placeholder="Enter command here...",
            disabled=st.session_state.test_running,
            key="custom_command_input"
        )
    
    with col2:
        st.write("")
        st.write("")
        submit_button = st.form_submit_button(
            "▶️ Run Command", 
            type="primary", 
            disabled=st.session_state.test_running
        )
    
    # Execute command when form is submitted (Enter or button click)
    if submit_button and custom_command.strip():
        if not st.session_state.test_running:
            success, output = run_command_async(custom_command)
            if success:
                st.success(f"Command executed: {custom_command}")
            else:
                st.error(f"Command failed: {output}")

# Allure Results Quick Actions
st.header("📋 Allure Results")
allure_path = Path("allure-results")
if allure_path.exists():
    result_folders = [f.name for f in allure_path.iterdir() if f.is_dir()]
    if result_folders:
        col1, col2 = st.columns(2)
        
        with col1:
            selected_folder = st.selectbox("Select results folder:", result_folders)
            
        with col2:
            st.write("")
            if st.button("📊 Generate Allure Report"):
                cmd = f"allure generate --single-file allure-results/{selected_folder} -o allure-report"
                success, output = run_command_async(cmd)
                if success:
                    # Find generated report file and offer download
                    report_dir = Path("allure-report")
                    if report_dir.exists():
                        # Look for HTML files in the report directory
                        html_files = list(report_dir.glob("*.html"))
                        if html_files:
                            report_file = html_files[0]  # Take the first HTML file
                            with open(report_file, "rb") as f:
                                st.download_button(
                                    label="⬇️ Download Report",
                                    data=f.read(),
                                    file_name=f"allure-report-{selected_folder}.html",
                                    mime="text/html"
                                )
                        else:
                            # Fallback: try index.html
                            report_file = report_dir / "index.html"
                            if report_file.exists():
                                with open(report_file, "rb") as f:
                                    st.download_button(
                                        label="⬇️ Download Report",
                                        data=f.read(),
                                        file_name=f"allure-report-{selected_folder}.html",
                                        mime="text/html"
                                    )
                            else:
                                st.error("Report generated but HTML file not found")
                    else:
                        st.error("Report directory not found")
                else:
                    st.error(f"Failed to generate report: {output}")
            
            if st.button("🔍 Extract Build Errors"):
                cmd = f"python extract_build_errors.py allure-results/{selected_folder}"
                success, output = run_command_async(cmd)
                if success:
                    # Find generated errors file and offer download
                    errors_file = Path(f"build_errors_{selected_folder}.txt")
                    if errors_file.exists():
                        with open(errors_file, "rb") as f:
                            st.download_button(
                                label="⬇️ Download Errors",
                                data=f.read(),
                                file_name=f"build_errors_{selected_folder}.txt",
                                mime="text/plain"
                            )
                else:
                    st.error(f"Failed to extract errors: {output}")
    else:
        st.info("No result folders found in allure-results")
else:
    st.info("allure-results folder not found")

# Status section
st.header("📊 Status & Output")

if st.session_state.test_running:
    st.warning("🔄 Command is running...")
    # Update live output
    if update_live_output():
        st.rerun()
else:
    st.success("✅ Ready for commands")

# Live Output section
st.header("📄 Live Command Output")
if st.session_state.test_running and st.session_state.live_output:
    # Create a container for live output
    output_container = st.container()
    with output_container:
        st.code(st.session_state.live_output, language="bash")
        
    # Auto-scroll to bottom (simulate)
    if st.session_state.test_running:
        time.sleep(0.5)
        st.rerun()
        
elif st.session_state.last_output:
    st.code(st.session_state.last_output, language="bash")
else:
    st.info("No output yet. Run a command to see results.")

# Auto-refresh for live updates
if st.session_state.test_running:
    time.sleep(1)
    st.rerun()

# Footer
st.markdown("---")
st.markdown("**weby-gen-tester** - Powered by Streamlit")

# Auto-refresh during command execution
if st.session_state.test_running:
    st_autorefresh(interval=500, key="live_update")