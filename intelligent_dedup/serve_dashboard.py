"""
serve_dashboard.py
================================================================================
A simple local server to host the Intelligent Dedup Coverage Dashboard.
This enables the "Run Tests" button in the UI to trigger the local test suite.

Usage:
    python serve_dashboard.py [--port 5000]
================================================================================
"""
import http.server
import socketserver
import os
import subprocess
import json
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).parent.resolve()
HISTORY_DIR = ROOT / "coverage_history"

class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        # We serve directly from the history directory so links match disk layout
        super().__init__(*args, directory=str(HISTORY_DIR), **kwargs)

    def do_GET(self):
        # Already in HISTORY_DIR, so root is index.html
        if self.path == "/":
            self.path = "/index.html"
        return super().do_GET()

    def do_POST(self):
        if self.path == "/run-tests":
            try:
                print("\n[Server] Triggering test suite via PowerShell...")
                # Script is in the parent directory relative to HISTORY_DIR
                script_path = ROOT / "run_tests.ps1"
                process = subprocess.run(
                    ["powershell.exe", "-ExecutionPolicy", "Bypass", "-File", str(script_path), "-NoOpen"],
                    cwd=str(ROOT),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding='utf-8',
                    errors='replace'
                )
                
                output_captured = process.stdout
                if process.returncode == 0:
                    print("[Server] Test suite completed successfully.")
                else:
                    print(f"[Server] Test suite failed with code {process.returncode}")

                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                
                resp = {
                    "status": "success" if process.returncode == 0 else "failure",
                    "code": process.returncode,
                    "output": output_captured
                }
                self.wfile.write(json.dumps(resp).encode())
                
            except Exception as e:
                print(f"[Server] Error running tests: {e}")
                self.send_response(500)
                self.end_headers()
                self.wfile.write(str(e).encode())
        else:
            self.send_response(404)
            self.end_headers()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5000)
    args = parser.parse_args()

    # Ensure dashboard exists before serving
    if not (HISTORY_DIR / "index.html").exists():
        print("[Server] Dashboard not found. Running initial generation...")
        subprocess.run([sys.executable, "generate_coverage_dashboard.py"], cwd=str(ROOT))

    print(f"\n============================================================")
    print(f"  Intelligent Dedup Dashboard Server")
    print(f"  URL: http://localhost:{args.port}")
    print(f"============================================================\n")
    
    with socketserver.TCPServer(("", args.port), DashboardHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n[Server] Shutting down.")
            httpd.shutdown()

if __name__ == "__main__":
    main()
