import os
import pickle
import datetime
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from mcp.server.fastmcp import FastMCP

# We added the Calendar scope!
# IMPORTANT: Delete token.pickle so the user is prompted to re-auth with the new scope.
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/calendar.readonly'
]

def get_google_services():
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
            
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists('credentials.json'):
                raise FileNotFoundError("Missing 'credentials.json'.")
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    gmail = build('gmail', 'v1', credentials=creds)
    calendar = build('calendar', 'v3', credentials=creds)
    return gmail, calendar

mcp = FastMCP("Workspace Comms & Logistics")

@mcp.tool()
def list_latest_emails(max_results: int = 10) -> str:
    """Retrieves the latest emails from the user's Gmail inbox."""
    try:
        gmail, _ = get_google_services()
        results = gmail.users().messages().list(userId='me', labelIds=['INBOX'], maxResults=max_results).execute()
        messages = results.get('messages', [])

        if not messages:
            return "No messages found."
            
        output = []
        for message in messages:
            msg = gmail.users().messages().get(userId='me', id=message['id'], format='metadata', metadataHeaders=['Subject', 'From', 'Date']).execute()
            headers = msg['payload']['headers']
            subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
            sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown Sender')
            output.append(f"From: {sender}\nSubject: {subject}\nSnippet: {msg.get('snippet', '')}\n---")
            
        return "\n".join(output)
    except Exception as e:
        return f"Error connecting to Gmail: {str(e)}"

@mcp.tool()
def get_upcoming_calendar_events(max_results: int = 10) -> str:
    """Retrieves the user's upcoming Google Calendar events."""
    try:
        _, calendar = get_google_services()
        now = datetime.datetime.utcnow().isoformat() + 'Z'  # 'Z' indicates UTC time
        events_result = calendar.events().list(calendarId='primary', timeMin=now,
                                              maxResults=max_results, singleEvents=True,
                                              orderBy='startTime').execute()
        events = events_result.get('items', [])

        if not events:
            return "No upcoming events found."
            
        output = []
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            output.append(f"{start} - {event['summary']}")
            
        return "\n".join(output)
    except Exception as e:
        return f"Error connecting to Calendar: {str(e)}"

if __name__ == "__main__":
    mcp.run()
