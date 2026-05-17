#!/usr/bin/env python3
"""
start.py — pokreni ovo. Sve ostalo radi samo.
"""
import subprocess, sys, time, webbrowser
from pathlib import Path

HERE   = Path(__file__).resolve().parent
PYTHON = sys.executable
URL    = "http://localhost:5000"

print("Starting AI Arena...")
proc = subprocess.Popen([PYTHON, str(HERE / "server.py")])
time.sleep(2)
webbrowser.open(URL)
print(f"Opened {URL}")
print("Press Ctrl+C to stop.\n")
try:
    proc.wait()
except KeyboardInterrupt:
    proc.terminate()
    print("\nStopped.")
