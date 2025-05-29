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

# Configure Streamlit page
st.set_page_config(
    page_title="NextJS Web Tester",
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

def run_command_async(command):
    """Run command asynchronously with real-time output"""
    try:
        st.session_state.test_running = True
        st.session_state.live_output = f"Starting command: {command}\n"
        
        # Add to history
        st.session_state.command_history.append({
            'command': command,
            'timestamp': datetime.now().isoformat(),
            'status': 'running'
        })
        
        # Start process
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=True,
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
    """Stop currently running command"""
    if st.session_state.current_process:
        try:
            st.session_state.current_process.terminate()
            st.session_state.live_output += "\n[STOPPED] Command terminated by user\n"
            st.session_state.test_running = False
            st.session_state.current_process = None
            
            # Update history
            if st.session_state.command_history:
                st.session_state.command_history[-1]['status'] = 'stopped'
                
        except Exception as e:
            st.session_state.live_output += f"\n[ERROR] Failed to stop command: {str(e)}\n"

def generate_allure_report(folder_name, output_format='html'):
    """Generate Allure report in specified format"""
    try:
        # Check if folder exists
        folder_path = Path(folder_name)
        if not folder_path.exists():
            return False, f"Folder '{folder_name}' does not exist"
        
        # Check if folder contains allure results
        if not any(folder_path.glob("*.json")):
            return False, f"No Allure result files found in '{folder_name}'"
        
        # Generate report filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if output_format == 'single-file':
            report_filename = f"allure_report_{timestamp}.html"
            command = f"allure generate {folder_name} --single-file --output temp_report && mv temp_report/index.html {report_filename} && rm -rf temp_report"
        else:
            report_dir = f"allure_report_{timestamp}"
            command = f"allure generate {folder_name} --output {report_dir}"
            report_filename = report_dir
        
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            if Path(report_filename).exists():
                return True, report_filename
            else:
                return False, "Report file/directory was not created"
        else:
            return False, f"Allure command failed: {result.stderr}"
            
    except Exception as e:
        return False, f"Error generating report: {str(e)}"

def get_available_folders():
    """Get list of available folders that might contain Allure results"""
    folders = []
    current_dir = Path(".")
    
    for item in current_dir.iterdir():
        if item.is_dir() and not item.name.startswith('.'):
            # Check if folder contains JSON files (potential Allure results)
            if any(item.glob("*.json")):
                folders.append(item.name)
    
    return folders

def clean_allure_results(folder_name):
    """Clean Allure results folder"""
    try:
        folder_path = Path(folder_name)
        if folder_path.exists():
            import shutil
            shutil.rmtree(folder_path)
            folder_path.mkdir()
            return True, f"Cleaned folder '{folder_name}'"
        else:
            return False, f"Folder '{folder_name}' does not exist"
    except Exception as e:
        return False, f"Error cleaning folder: {str(e)}"

# Sidebar with system info
with st.sidebar:
    st.header("📊 System Info")
    st.info(f"**Python:** {sys.version.split()[0]}")
    st.info(f"**Working Dir:** {os.getcwd()}")
    st.info(f"**Time:** {datetime.now().strftime('%H:%M:%S')}")
    
    if st.button("🔄 Refresh"):
        st.rerun()
    
    # Command history
    st.header("📜 Command History")
    if st.session_state.command_history:
        for i, cmd in enumerate(reversed(st.session_state.command_history[-5:])):
            status_emoji = {
                'running': '🔄',
                'completed': '✅' if cmd.get('returncode', 0) == 0 else '❌',
                'error': '💥',
                'stopped': '⏹️'
            }.get(cmd['status'], '❓')
            
            st.text(f"{status_emoji} {cmd['command'][:30]}...")
    else:
        st.text("No commands yet")

# Main content area
st.header("🧪 Test Commands")

col1, col2 = st.columns([1, 1])

with col1:
    test_commands = [
        ("Check Pytest", "pytest --version"),
        ("List Files", "ls -la"),
        ("Check Playwright", "python3 -c \"import playwright; print('Playwright OK')\"")
    ]
    
    for label, cmd in test_commands:
        if st.button(label, key=f"test_{cmd}", disabled=st.session_state.test_running):
            success, output = run_command_async(cmd)
            if success:
                st.success(f"Command started: {label}")
            else:
                st.error(f"Command failed to start: {label}")
            st.rerun()

with col2:
    test_commands_2 = [
        ("Run All Tests", "pytest test_nextjs_site.py -v"),
        ("Generate Allure Results", "pytest test_nextjs_site.py --alluredir=allure-results"),
        ("Run Tests + Allure", "pytest test_nextjs_site.py -v --alluredir=allure-results")
    ]
    
    for label, cmd in test_commands_2:
        if st.button(label, key=f"test2_{cmd}", disabled=st.session_state.test_running):
            success, output = run_command_async(cmd)
            if success:
                st.success(f"Command started: {label}")
            else:
                st.error(f"Command failed to start: {label}")
            st.rerun()

# Enhanced Allure Management Section
st.header("📊 Allure Report Management")

# Allure folder selection
col1, col2, col3 = st.columns([2, 1, 1])

with col1:
    available_folders = get_available_folders()
    
    if available_folders:
        folder_option = st.selectbox(
            "Select folder with Allure results:",
            options=["Custom..."] + available_folders,
            disabled=st.session_state.test_running
        )
        
        if folder_option == "Custom...":
            allure_folder = st.text_input(
                "Enter folder name:",
                value="allure-results",
                placeholder="e.g., allure-results",
                disabled=st.session_state.test_running
            )
        else:
            allure_folder = folder_option
    else:
        allure_folder = st.text_input(
            "Enter folder name with Allure results:",
            value="allure-results",
            placeholder="e.g., allure-results",
            disabled=st.session_state.test_running
        )

with col2:
    st.write("")
    st.write("")
    if st.button("📁 List Folders", disabled=st.session_state.test_running):
        folders = get_available_folders()
        if folders:
            st.success("Available folders with JSON files:")
            for folder in folders:
                json_count = len(list(Path(folder).glob("*.json")))
                st.text(f"📁 {folder} ({json_count} files)")
        else:
            st.info("No folders with JSON files found")

with col3:
    st.write("")
    st.write("")
    if st.button("🗑️ Clean Results", disabled=st.session_state.test_running):
        if allure_folder.strip():
            success, message = clean_allure_results(allure_folder.strip())
            if success:
                st.success(message)
            else:
                st.error(message)
        else:
            st.warning("Please enter a folder name")

# Report generation options
st.subheader("📄 Generate Reports")

col1, col2, col3 = st.columns([1, 1, 1])

with col1:
    if st.button("📄 Single File Report", type="primary", disabled=st.session_state.test_running):
        if allure_folder.strip():
            with st.spinner("Generating single-file Allure report..."):
                success, result = generate_allure_report(allure_folder.strip(), 'single-file')
                
            if success:
                st.success(f"Report generated: {result}")
                
                # Read the generated file for download
                try:
                    with open(result, 'rb') as file:
                        file_data = file.read()
                    
                    st.download_button(
                        label="⬇️ Download HTML Report",
                        data=file_data,
                        file_name=result,
                        mime="text/html",
                        key="download_single_report"
                    )
                    
                    # Show file info
                    file_size = len(file_data) / 1024  # KB
                    st.info(f"File size: {file_size:.1f} KB")
                    
                except Exception as e:
                    st.error(f"Error reading report file: {str(e)}")
            else:
                st.error(f"Failed to generate report: {result}")
        else:
            st.warning("Please enter a folder name")

with col2:
    if st.button("📁 Full Report Directory", disabled=st.session_state.test_running):
        if allure_folder.strip():
            with st.spinner("Generating full Allure report..."):
                success, result = generate_allure_report(allure_folder.strip(), 'directory')
                
            if success:
                st.success(f"Report directory created: {result}")
                st.info(f"Open {result}/index.html in browser to view")
            else:
                st.error(f"Failed to generate report: {result}")
        else:
            st.warning("Please enter a folder name")

with col3:
    if st.button("🔄 Serve Report", disabled=st.session_state.test_running):
        if allure_folder.strip():
            serve_command = f"allure serve {allure_folder.strip()}"
            success, output = run_command_async(serve_command)
            if success:
                st.success("Allure serve started")
                st.info("Check the output below for the server URL")
            else:
                st.error("Failed to start Allure serve")
            st.rerun()
        else:
            st.warning("Please enter a folder name")

# Custom command section
st.header("💻 Custom Command")
col1, col2, col3 = st.columns([3, 1, 1])

with col1:
    custom_command = st.text_input(
        "Enter any shell command:", 
        value="ls -la",
        placeholder="Enter command here...",
        disabled=st.session_state.test_running
    )

with col2:
    st.write("")
    st.write("")
    if st.button("▶️ Run Command", type="primary", disabled=st.session_state.test_running):
        if custom_command.strip():
            success, output = run_command_async(custom_command)
            if success:
                st.success("Custom command started")
            else:
                st.error("Custom command failed to start")
            st.rerun()
        else:
            st.warning("Please enter a command")

with col3:
    st.write("")
    st.write("")
    if st.button("⏹️ Stop", disabled=not st.session_state.test_running):
        stop_current_command()
        st.rerun()

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

# Results section (expandable)
if st.session_state.test_results:
    with st.expander("📋 Detailed Results (JSON)"):
        st.json(st.session_state.test_results)

# Auto-refresh for live updates
if st.session_state.test_running:
    time.sleep(1)
    st.rerun()

# Footer
st.markdown("---")
st.markdown("**NextJS Web Tester** - Streamlit Edition with Enhanced Allure Management | Built with ❤️")

# Auto-refresh during command execution
if st.session_state.test_running:
    st_autorefresh(interval=500, key="live_update")