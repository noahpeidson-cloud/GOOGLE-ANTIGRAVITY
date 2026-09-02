import http.server
import socketserver
import json
import sqlite3
import os
from urllib.parse import urlparse, parse_qs
import threading

PORT = 8999
MEDIA_DIR = r"C:\Users\noahp\Downloads\Quick Share"
DB_FILE = "booth_telemetry.db"

# Initialize SQLite
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS edits
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  filename TEXT,
                  in_point REAL,
                  out_point REAL,
                  tags TEXT,
                  notes TEXT,
                  ai_proposed_in REAL,
                  ai_proposed_out REAL,
                  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

init_db()

class BoothHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=MEDIA_DIR, **kwargs)

    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_POST(self):
        if self.path == '/api/save_edit':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute('''INSERT INTO edits 
                         (filename, in_point, out_point, tags, notes, ai_proposed_in, ai_proposed_out) 
                         VALUES (?, ?, ?, ?, ?, ?, ?)''',
                      (data.get('filename'), data.get('in_point'), data.get('out_point'), 
                       json.dumps(data.get('tags', [])), data.get('notes'),
                       data.get('ai_proposed_in'), data.get('ai_proposed_out')))
            conn.commit()
            conn.close()
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "success"}).encode())
            
        elif self.path == '/api/request_review':
            # This endpoint signals the watchdog to alert the agent
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            
            # We insert a special marker or just touch a file
            with open('REVIEW_REQUESTED.flag', 'w') as f:
                f.write(json.dumps(data))
                
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "review_requested"}).encode())
        else:
            self.send_error(404)

if __name__ == '__main__':
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), BoothHandler) as httpd:
        print(f"Booth Server running on port {PORT}. Serving {MEDIA_DIR}")
        httpd.serve_forever()
