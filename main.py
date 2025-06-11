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

import threading
import select
import sys

def stream_output(process, output_queue):
    """Stream output from process to queue with real-time handling"""
    try:
        # Use threading to handle stdout and stderr simultaneously
        def read_stdout():
            try:
                for line in iter(process.stdout.readline, ''):
                    if line:
                        output_queue.put(('stdout', line))
            except Exception as e:
                output_queue.put(('error', f'stdout error: {str(e)}'))
        
        def read_stderr():
            try:
                for line in iter(process.stderr.readline, ''):
                    if line:
                        output_queue.put(('stderr', line))
            except Exception as e:
                output_queue.put(('error', f'stderr error: {str(e)}'))
        
        # Start both threads
        stdout_thread = threading.Thread(target=read_stdout)
        stderr_thread = threading.Thread(target=read_stderr)
        
        stdout_thread.daemon = True
        stderr_thread.daemon = True
        
        stdout_thread.start()
        stderr_thread.start()
        
        # Wait for process to complete
        process.wait()
        
        # Wait for threads to finish
        stdout_thread.join(timeout=1)
        stderr_thread.join(timeout=1)
        
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
        # CRITICAL: Set test_running to True FIRST
        st.session_state.test_running = True
        st.session_state.live_output = f"Starting command: {command}\n"
        
        # Add command to history
        st.session_state.command_history.append({
            'command': command,
            'timestamp': datetime.now().isoformat(),
            'status': 'running'
        })
        
        # Use shlex.split for safer command parsing
        cmd_parts = shlex.split(command)
        
        # Start process WITHOUT shell=True for better security
        process = subprocess.Popen(
            cmd_parts,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=0,  # Unbuffered for real-time output
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
        st.session_state.test_running = False  # Reset on error
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
                
                # CRITICAL: Reset state and force interface update
                st.session_state.test_running = False
                st.session_state.current_process = None
                
                # Force interface update
                st.rerun()
                
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
# Add debug information to sidebar
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
# Add explicit state check in form section
with st.form(key="command_form", clear_on_submit=False):
    # Explicitly check state before displaying form
    form_disabled = st.session_state.get('test_running', False)
    
    col1, col2 = st.columns([4, 1])
    
    with col1:
        custom_command = st.text_input(
            "Enter any shell command:", 
            value="ls -la",
            placeholder="Enter command here...",
            disabled=form_disabled,  # Use explicit variable
            key="custom_command_input"
        )
    
    with col2:
        st.write("")
        st.write("")
        submit_button = st.form_submit_button(
            "▶️ Run Command", 
            type="primary", 
            disabled=form_disabled  # Use the same variable
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
                # Fixed: use correct path to results
                cmd = f"allure generate allure-results/{selected_folder} -o allure-report --single-file --clean"
                success, output = run_command_async(cmd)
                if success:
                    st.success("Allure report generation started!")
                    st.info("Check the command output below. When completed, refresh the page to see download options.")
                else:
                    st.error(f"Failed to generate report: {output}")
            
            if st.button("🔍 Extract Build Errors"):
                cmd = f"python extract_build_errors.py allure-results/{selected_folder}"
                success, output = run_command_async(cmd)
                if success:
                    st.success("Build error extraction started!")
                    st.info("Check the command output below. When completed, refresh the page to see download options.")
                else:
                    st.error(f"Failed to extract errors: {output}")
        
        # Separate section for downloads (always visible)
        st.subheader("📥 Available Downloads")
        
        # Check for existing Allure reports
        report_dir = Path("allure-report")
        if report_dir.exists():
            html_files = list(report_dir.glob("*.html"))
            if html_files:
                report_file = html_files[0]
                with open(report_file, "rb") as f:
                    st.download_button(
                        label="⬇️ Download Allure Report",
                        data=f.read(),
                        file_name=f"allure-report-{selected_folder}.html",
                        mime="text/html",
                        key=f"download_report_{selected_folder}"
                    )
            elif (report_dir / "index.html").exists():
                with open(report_dir / "index.html", "rb") as f:
                    st.download_button(
                        label="⬇️ Download Allure Report",
                        data=f.read(),
                        file_name=f"allure-report-{selected_folder}.html",
                        mime="text/html",
                        key=f"download_report_index_{selected_folder}"
                    )
        
        # Check for existing error files
        # Fixed: search for correct error file
        # First check general build_errors_summary.txt file
        summary_file = Path("build_errors_summary.txt")
        if summary_file.exists():
            with open(summary_file, "rb") as f:
                st.download_button(
                    label="⬇️ Download Build Errors Summary",
                    data=f.read(),
                    file_name="build_errors_summary.txt",
                    mime="text/plain",
                    key="download_errors_summary"
                )
        
        # Also check file with folder name (if it exists)
        errors_file = Path(f"build_errors_{selected_folder}.txt")
        if errors_file.exists():
            with open(errors_file, "rb") as f:
                st.download_button(
                    label=f"⬇️ Download Build Errors ({selected_folder})",
                    data=f.read(),
                    file_name=f"build_errors_{selected_folder}.txt",
                    mime="text/plain",
                    key=f"download_errors_{selected_folder}"
                )
        
        # Show available files for debugging
        with st.expander("🔍 Debug: Available Files"):
            st.write("**Allure report directory:**")
            if report_dir.exists():
                for file in report_dir.iterdir():
                    st.text(f"  - {file.name}")
            else:
                st.text("  Directory not found")
            
            st.write("**Error files:**")
            error_files = list(Path(".").glob("build_errors_*.txt"))
            if error_files:
                for file in error_files:
                    st.text(f"  - {file.name}")
            else:
                st.text("  No error files found")
    else:
        st.info("No result folders found in allure-results")
else:
    st.info("allure-results folder not found")

# Status section
st.header("📊 Status & Output")

# Always update output first
update_live_output()

# Simple status check
if st.session_state.test_running:
    st.warning("🔄 Command is running...")
else:
    st.success("✅ Ready for commands")

# Live Output section
st.header("📄 Live Command Output")
if st.session_state.test_running:
    if st.session_state.live_output:
        st.code(st.session_state.live_output, language="bash")
    else:
        st.info("Command is running, waiting for output...")
else:
    if st.session_state.last_output:
        st.code(st.session_state.last_output, language="bash")
    else:
        st.info("No output yet. Run a command to see results.")

# Footer
st.markdown("---")
st.markdown("**weby-gen-tester** - Powered by Streamlit")

# Simple auto-refresh logic
if st.session_state.test_running:
    st_autorefresh(interval=1000, key="live_update")
else:
    # Force one final refresh when command completes to unlock the form
    if 'command_just_completed' not in st.session_state:
        st.session_state.command_just_completed = False
    
    # Check if we just completed a command
    if (st.session_state.current_process is None and 
        st.session_state.command_history and 
        st.session_state.command_history[-1].get('status') == 'completed' and
        not st.session_state.command_just_completed):
        
        st.session_state.command_just_completed = True
        st.rerun()  # One final rerun to unlock the form