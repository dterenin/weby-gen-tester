import subprocess
import sys
import os
import signal
import time

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

if __name__ == "__main__":
    print("NextJS Web Tester is starting...")
    
    if check_dependencies():
        print("\n✓ All dependencies are available!")
        print("\nAvailable commands:")
        print("  • Run tests: pytest test_nextjs_site.py")
        print("  • Run with CSV: pytest test_nextjs_site.py --csv-input-field=your_file.csv")
        print("  • Generate Allure reports: pytest test_nextjs_site.py --alluredir=allure-results")
        print("\nContainer is ready and waiting for commands...")
    else:
        print("\n✗ Missing dependencies. Please install Node.js and pnpm.")
        sys.exit(1)
    
    # Keep the process alive with better resource usage
    try:
        while True:
            time.sleep(300)  # Sleep for 5 minutes instead of 1 hour
    except KeyboardInterrupt:
        print('\nExiting...')

    subprocess.run(["pytest", "test_nextjs_site.py", "-v"])
    
    # Keep the process alive
    import time
    while True:
        time.sleep(3600)  # Sleep for 1 hour