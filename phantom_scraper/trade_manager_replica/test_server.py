#!/usr/bin/env python3
"""
Simple test server to serve the React frontend
This bypasses Flask and serves the built files directly
"""

import http.server
import socketserver
import os
import sys

# Change to frontend/dist directory
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'frontend', 'dist')
os.chdir(FRONTEND_DIR)

PORT = 8080

class MyHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        # Add CORS headers
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()
    
    def do_GET(self):
        # Serve index.html for all routes (SPA support)
        if self.path.startswith('/api/'):
            # API routes - proxy or return 404
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'API not available - use Flask backend')
            return
        
        # For SPA, serve index.html for all routes
        if '.' not in os.path.basename(self.path) or self.path == '/':
            self.path = '/index.html'
        
        return super().do_GET()

if __name__ == '__main__':
    if not os.path.exists(FRONTEND_DIR):
        print(f"❌ Frontend build not found: {FRONTEND_DIR}")
        print("Run: cd frontend && npm run build")
        sys.exit(1)
    
    os.chdir(FRONTEND_DIR)
    print(f"📁 Serving from: {FRONTEND_DIR}")
    print(f"🌐 Server: http://localhost:{PORT}")
    print(f"📝 Test: http://localhost:{PORT}/dashboard")
    print("Press Ctrl+C to stop")
    print("")
    
    with socketserver.TCPServer(("", PORT), MyHTTPRequestHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n✅ Server stopped")

