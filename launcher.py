"""
ANPR System Launcher
Starts both the detection system and web dashboard
"""

import subprocess
import time
import sys
import webbrowser
from threading import Thread

def start_anpr_system():
    """Start the main ANPR detection system"""
    print("Starting ANPR Detection System...")
    subprocess.run([sys.executable, "main.py"])

def start_web_interface():
    """Start the Flask web dashboard"""
    print("Starting Web Dashboard...")
    time.sleep(2)  # Give ANPR system time to initialize
    subprocess.run([sys.executable, "web_interface.py"])

def open_browser():
    """Open browser to dashboard after startup"""
    time.sleep(5)  # Wait for Flask to start
    print("\nOpening dashboard in browser...")
    webbrowser.open('http://localhost:5000')

if __name__ == "__main__":
    print("=" * 60)
    print("NIGERIAN ANPR SYSTEM LAUNCHER")
    print("=" * 60)
    print()
    print("This will start:")
    print("1. ANPR Detection System (OpenCV window)")
    print("2. Web Dashboard (http://localhost:5000)")
    print()
    print("Press Ctrl+C to stop all services")
    print("=" * 60)
    print()
    
    try:
        # Start browser opener in background
        browser_thread = Thread(target=open_browser, daemon=True)
        browser_thread.start()
        
        # Start web interface in background
        web_thread = Thread(target=start_web_interface, daemon=True)
        web_thread.start()
        
        # Start ANPR system in foreground (blocks until quit)
        start_anpr_system()
        
    except KeyboardInterrupt:
        print("\n\nShutting down ANPR System...")
        print("Goodbye!")