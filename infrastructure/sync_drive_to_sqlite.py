import os
import time
import sqlite3
import pickle
import random
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Scope required for read-only metadata access
SCOPES = ['https://www.googleapis.com/auth/drive.metadata.readonly']
DB_PATH = 'G:/My Drive/GOOGLE ANTIGRAVITY/apps/inbox.db'

def get_drive_service():
    creds = None
    if os.path.exists('token_drive.pickle'):
        with open('token_drive.pickle', 'rb') as token:
            creds = pickle.load(token)
            
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists('credentials.json'):
                raise FileNotFoundError("Missing 'credentials.json'.")
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token_drive.pickle', 'wb') as token:
            pickle.dump(creds, token)

    return build('drive', 'v3', credentials=creds)

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # Dynamic TEXT for file_id due to 33-44 char variance
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS drive_metadata (
            file_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            mime_type TEXT,
            modified_time DATETIME,
            size INTEGER,
            parents TEXT,
            last_synced DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sync_state (
            state_key TEXT PRIMARY KEY,
            state_value TEXT
        )
    ''')
    conn.commit()
    return conn

def robust_execute(request, max_retries=6):
    """Executes a Google API request with Truncated Exponential Backoff."""
    delay = 1
    for attempt in range(max_retries):
        try:
            return request.execute()
        except HttpError as error:
            if error.resp.status in [403, 429]:
                print(f"[-] Rate limit hit (Status {error.resp.status}). Retrying in {delay}s...")
                time.sleep(delay + random.uniform(0, 1))
                delay = min(delay * 2, 32) # Cap at 32 seconds
            else:
                raise error
    raise Exception("Max retries exceeded during API request.")

def perform_initial_backfill(service, conn):
    print("[*] Starting initial metadata backfill...")
    cursor = conn.cursor()
    page_token = None
    total_indexed = 0

    while True:
        request = service.files().list(
            pageSize=1000,
            fields="nextPageToken, files(id, name, mimeType, modifiedTime, size, parents)",
            pageToken=page_token,
            q="trashed=false"
        )
        results = robust_execute(request)
        files = results.get('files', [])

        for f in files:
            parents = ",".join(f.get('parents', []))
            cursor.execute('''
                INSERT OR REPLACE INTO drive_metadata 
                (file_id, name, mime_type, modified_time, size, parents, last_synced)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (
                f.get('id'), f.get('name'), f.get('mimeType'), 
                f.get('modifiedTime'), f.get('size'), parents
            ))
            total_indexed += 1

        conn.commit()
        print(f"[*] Indexed {total_indexed} files...")

        page_token = results.get('nextPageToken', None)
        if not page_token:
            break

    # Get the start page token for future delta syncs
    start_token_req = service.changes().getStartPageToken()
    start_token_res = robust_execute(start_token_req)
    saved_token = start_token_res.get('startPageToken')
    
    cursor.execute("INSERT OR REPLACE INTO sync_state (state_key, state_value) VALUES ('pageToken', ?)", (saved_token,))
    conn.commit()
    print(f"[*] Initial backfill complete. Total files: {total_indexed}. Saved page token.")

def poll_for_changes(service, conn):
    cursor = conn.cursor()
    cursor.execute("SELECT state_value FROM sync_state WHERE state_key = 'pageToken'")
    row = cursor.fetchone()
    
    if not row:
        print("[!] No pageToken found. Running initial backfill first.")
        perform_initial_backfill(service, conn)
        return

    saved_token = row[0]
    print(f"[*] Polling for changes using token: {saved_token}")

    while True:
        try:
            print(f"[*] Fetching changes...")
            page_token = saved_token
            while page_token:
                request = service.changes().list(pageToken=page_token, spaces='drive')
                results = robust_execute(request)
                
                for change in results.get('changes', []):
                    if change.get('removed'):
                        cursor.execute("DELETE FROM drive_metadata WHERE file_id = ?", (change.get('fileId'),))
                        print(f"[-] Removed file {change.get('fileId')}")
                    else:
                        f = change.get('file')
                        if f:
                            parents = ",".join(f.get('parents', []))
                            cursor.execute('''
                                INSERT OR REPLACE INTO drive_metadata 
                                (file_id, name, mime_type, modified_time, size, parents, last_synced)
                                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                            ''', (
                                f.get('id'), f.get('name'), f.get('mimeType'), 
                                f.get('modifiedTime'), f.get('size'), parents
                            ))
                            print(f"[+] Updated file: {f.get('name')}")

                if 'newStartPageToken' in results:
                    saved_token = results.get('newStartPageToken')
                    cursor.execute("UPDATE sync_state SET state_value = ? WHERE state_key = 'pageToken'", (saved_token,))
                    conn.commit()

                page_token = results.get('nextPageToken')

            print("[*] Delta sync complete. Sleeping for 5 minutes...")
            time.sleep(300) # Sleep for 5 minutes

        except Exception as e:
            print(f"[!] Error during polling: {e}. Retrying in 60 seconds...")
            time.sleep(60)

if __name__ == '__main__':
    conn = init_db()
    service = get_drive_service()
    
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM drive_metadata LIMIT 1")
    if not cursor.fetchone():
        perform_initial_backfill(service, conn)
    else:
        # Start continuous 5-minute polling loop
        poll_for_changes(service, conn)
