import streamlit as st
import subprocess
import sys
import os
import threading
import time
from datetime import datetime
import json

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

def run_command(command):
    """Run command and update session state"""
    try:
        st.session_state.test_running = True
        
        # Add to history
        st.session_state.command_history.append({
            'command': command,
            'timestamp': datetime.now().isoformat(),
            'status': 'running'
        })
        
        # Run command
        result = subprocess.run(
            command, 
            capture_output=True, 
            text=True, 
            shell=True
        )
        
        # Update output
        output = f"Command: {command}\n\nSTDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}\n\nReturn code: {result.returncode}"
        st.session_state.last_output = output
        
        # Update results
        st.session_state.test_results = {
            'returncode': result.returncode,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'timestamp': datetime.now().isoformat(),
            'command': command
        }
        
        # Update history
        st.session_state.command_history[-1]['status'] = 'completed'
        st.session_state.command_history[-1]['returncode'] = result.returncode
        
        return True, output
        
    except Exception as e:
        error_msg = f"Error running command '{command}': {str(e)}"
        st.session_state.last_output = error_msg
        st.session_state.test_results = {
            'error': str(e),
            'timestamp': datetime.now().isoformat(),
            'command': command
        }
        
        # Update history
        if st.session_state.command_history:
            st.session_state.command_history[-1]['status'] = 'error'
            st.session_state.command_history[-1]['error'] = str(e)
        
        return False, error_msg
    finally:
        st.session_state.test_running = False

# Main UI
st.title("🧪 NextJS Web Tester")
st.markdown("**Debug Interface - Streamlit Edition**")

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
        if st.button(label, key=f"sys_{cmd}"):
            with st.spinner(f"Running: {cmd}"):
                success, output = run_command(cmd)
            if success:
                st.success(f"Command completed: {label}")
            else:
                st.error(f"Command failed: {label}")
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
        if st.button(label, key=f"test_{cmd}"):
            with st.spinner(f"Running: {cmd}"):
                success, output = run_command(cmd)
            if success:
                st.success(f"Command completed: {label}")
            else:
                st.error(f"Command failed: {label}")
            st.rerun()

# Custom command section
st.header("💻 Custom Command")
col1, col2 = st.columns([3, 1])

with col1:
    custom_command = st.text_input(
        "Enter any shell command:", 
        value="ls -la",
        placeholder="Enter command here..."
    )

with col2:
    st.write("")
    st.write("")
    if st.button("▶️ Run Command", type="primary"):
        if custom_command.strip():
            with st.spinner(f"Running: {custom_command}"):
                success, output = run_command(custom_command)
            if success:
                st.success("Custom command completed")
            else:
                st.error("Custom command failed")
            st.rerun()
        else:
            st.warning("Please enter a command")

# Status section
st.header("📊 Status & Output")

if st.session_state.test_running:
    st.warning("🔄 Command is running...")
else:
    st.success("✅ Ready for commands")

# Output section
st.header("📄 Command Output")
if st.session_state.last_output:
    st.code(st.session_state.last_output, language="bash")
else:
    st.info("No output yet. Run a command to see results.")

# Results section (expandable)
if st.session_state.test_results:
    with st.expander("📋 Detailed Results (JSON)"):
        st.json(st.session_state.test_results)

# Auto-refresh option
if st.checkbox("🔄 Auto-refresh every 5 seconds"):
    time.sleep(5)
    st.rerun()

# Footer
st.markdown("---")
st.markdown("**NextJS Web Tester** - Streamlit Edition | Built with ❤️")