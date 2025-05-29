import streamlit as st
import subprocess
import sys
import os
import threading
import time
from datetime import datetime
import json
import queue
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
                'error': '💥'
            }.get(cmd['status'], '❓')
            
            st.text(f"{status_emoji} {cmd['command'][:30]}...")
    else:
        st.text("No commands yet")

# Main content area
col1, col2 = st.columns([1, 1])

with col1:
    st.header("🔧 System Check Commands")
    
    system_commands = [
        ("Check Python", "python3 --version"),
        ("Python Path", "which python3"),
        ("Find Node", "ls -la /usr/local/bin/ | grep node"),
        ("Check PATH", "echo $PATH"),
        ("Current User", "whoami"),
        ("Current Directory", "pwd")
    ]
    
    for label, cmd in system_commands:
        if st.button(label, key=f"sys_{cmd}", disabled=st.session_state.test_running):
            success, output = run_command_async(cmd)
            if success:
                st.success(f"Command started: {label}")
            else:
                st.error(f"Command failed to start: {label}")
            st.rerun()

with col2:
    st.header("🧪 Test Commands")
    
    test_commands = [
        ("Check Pytest", "pytest --version"),
        ("List Files", "ls -la"),
        ("Check Playwright", "python3 -c \"import playwright; print('Playwright OK')\""),
        ("Collect Tests", "pytest test_nextjs_site.py --collect-only"),
        ("Run Tests", "pytest test_nextjs_site.py -v"),
        ("Generate Allure Report", "pytest test_nextjs_site.py --alluredir=allure-results")
    ]
    
    for label, cmd in test_commands:
        if st.button(label, key=f"test_{cmd}", disabled=st.session_state.test_running):
            success, output = run_command_async(cmd)
            if success:
                st.success(f"Command started: {label}")
            else:
                st.error(f"Command failed to start: {label}")
            st.rerun()

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
st.markdown("**NextJS Web Tester** - Streamlit Edition with Real-time Output | Built with ❤️")

# В основном коде добавить:
if st.session_state.test_running:
    # Автообновление каждые 500ms во время выполнения команды
    st_autorefresh(interval=500, key="live_update")