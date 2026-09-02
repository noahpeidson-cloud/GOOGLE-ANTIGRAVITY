---
title: "Spark Orchestration Engine: Autonomous System Integration Brief"
target_environment: "Google Anti-Gravity IDE"
api_dependencies:
  - "Google Drive API v3"
  - "Google Sheets API v4"
  - "Blogger API v3"
  - "YouTube Data API v3"
python_dependencies:
  - "google-api-python-client>=2.100.0"
  - "google-auth-oauthlib>=1.1.0"
  - "librosa>=0.10.1"
  - "pedalboard>=0.8.1"
  - "playwright>=1.40.0"
  - "pydub>=0.25.1"
  - "exiftool>=0.3.5"
---

# Spark Orchestration Engine: Autonomous System Integration Brief

This document serves as the technical development specification and code repository guide for **Google Anti-Gravity IDE**. It details the exact software architecture, Python scripts, API integration payloads, and command-line execution sequences required to build and deploy the **Spark Orchestration Engine** as a fully autonomous, background-running content machine.

---

## Phase 1: Ingestion & Routing Daemon (Google Drive API & Metadata Routing)

The ingestion engine must continuously poll the Google Drive root incoming folder, extract media metadata, parse the attributes, and auto-route files into their correct location inside the 4-folder hybrid directory structure.

### 1.1 Ingestion Directory Architecture
The local or cloud-mapped directory layout to be managed by the daemon is defined as:
```text
/EDM_Content_Hub/
├── 01_RAW/                  <-- Direct Mobile Upload Ingestion Target
├── 02_IN_PROGRESS/          <-- Working files (untrimmed, audio stems, project files)
├── 03_READY/                <-- Master compiled 1080x1920 vertical exports
└── 04_ARCHIVE/              <-- Synced source footage and historical masters
```

### 1.2 Python Metadata Router Implementation
The following Python script must be set up to run as a cron job or a background service (`systemd`). It uses `google-api-python-client` to poll `01_RAW/`, extracts video EXIF/XMP metadata via `exiftool`, and moves the file to its destination using a standardized naming convention.

```python
import os
import sys
import re
import datetime
import subprocess
import json
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials

# Configuration Constants
SERVICE_ACCOUNT_FILE = 'credentials.json'
SCOPES = ['https://www.googleapis.com/auth/drive']
RAW_FOLDER_ID = 'YOUR_GOOGLE_DRIVE_01_RAW_FOLDER_ID'
IN_PROGRESS_FOLDER_ID = 'YOUR_GOOGLE_DRIVE_02_IN_PROGRESS_FOLDER_ID'

def get_drive_service():
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    return build('drive', 'v3', credentials=creds)

def download_temp_file(service, file_id, filename):
    temp_path = os.path.join('/tmp', filename)
    request = service.files().get_media(fileId=file_id)
    with open(temp_path, 'wb') as fh:
        fh.write(request.execute())
    return temp_path

def get_video_metadata(filepath):
    """
    Executes CLI ExifTool to extract precise video capture timestamps and coordinates.
    """
    try:
        cmd = ['exiftool', '-j', '-CreateDate', '-GPSPosition', '-VideoFrameRate', '-CompressorID', filepath]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        metadata = json.loads(result.stdout)[0]
        return metadata
    except Exception as e:
        print(f"Error extracting metadata from {filepath}: {e}")
        return {}

def generate_standardized_name(metadata, original_name):
    # Fallback to current time if CreateDate is missing
    create_date_str = metadata.get('CreateDate', '')
    if create_date_str:
        # Format: "YYYY:MM:DD HH:MM:SS" -> "YYYYMMDD"
        dt_match = re.search(r'(\d{4}):(\d{2}):(\d{2})', create_date_str)
        date_prefix = "".join(dt_match.groups()) if dt_match else datetime.date.today().strftime('%Y%m%d')
    else:
        date_prefix = datetime.date.today().strftime('%Y%m%d')

    # Detect video codec
    codec = metadata.get('CompressorID', 'H264')
    if codec == 'avc1': codec = 'H264'
    elif codec == 'hvc1': codec = 'HEVC'

    ext = os.path.splitext(original_name)[1]
    
    # Standard format: YYYYMMDD_[Artist/Event]_[Venue]_[City]_[Codec].[Ext]
    # Location/Artist defaults can be overriden via a lookup dict using GPS coordinates or folder labels
    gps = metadata.get('GPSPosition', '')
    location_tag = "LiveSet_Event"
    if gps:
        # Example GPS lookup: coordinates to event name (Osl/EDC/Stad)
        location_tag = lookup_gps_location(gps)

    clean_name = f"{date_prefix}_{location_tag}_Raw_{codec}{ext}"
    return clean_name

def lookup_gps_location(gps_str):
    # Geofencing coordinates (latitude/longitude boundaries) matching major EDM venues
    # Format "37 deg 46' 9.12\" N, 122 deg 28' 51.60\" W" -> San Francisco (Outside Lands)
    if "37 deg 46'" in gps_str:
        return "OutsideLands_SF"
    elif "36 deg 5'" in gps_str:
        return "EDC_LV"
    return "ClubVenue_Spotlight"

def route_and_rename_files():
    service = get_drive_service()
    
    # Query files in 01_RAW
    query = f"'{RAW_FOLDER_ID}' in parents and trashed = false"
    results = service.files().list(q=query, fields="files(id, name, mimeType)").execute()
    files = results.get('files', [])
    
    for file in files:
        if file['mimeType'].startswith('video/'):
            print(f"Processing ingestion for: {file['name']}")
            temp_file = download_temp_file(service, file['id'], file['name'])
            metadata = get_video_metadata(temp_file)
            new_name = generate_standardized_name(metadata, file['name'])
            
            # Move and Rename via Drive API
            # Retrieve parents to remove the old raw parent
            file_to_update = service.files().get(fileId=file['id'], fields='parents').execute()
            previous_parents = ",".join(file_to_update.get('parents', []))
            
            service.files().update(
                fileId=file['id'],
                addParents=IN_PROGRESS_FOLDER_ID,
                removeParents=previous_parents,
                body={'name': new_name},
                fields='id, parents, name'
            ).execute()
            
            os.remove(temp_file)
            print(f"Successfully routed {file['name']} to 02_IN_PROGRESS as {new_name}")

if __name__ == '__main__':
    route_and_rename_files()
```

---

## Phase 2: Headless Production Pipeline & Audio DSP

This module automates the entire video-editing process, converting widescreen festival captures into high-fidelity vertical drops using Python script components.

```text
+-------------------+      +-------------------+      +-------------------+
|     Raw Video     | ---> | Extract/Separate  | ---> |  Apply DSP Chain  |
|  (02_IN_PROGRESS) |      | Audio (Demucs CLI)|      |  (Pedalboard CLI) |
+-------------------+      +-------------------+      +-------------------+
                                                                |
+-------------------+      +-------------------+                |
|   Final Export    | <--- | FFmpeg Video Crop | <--------------+
|    (03_READY)     |      |  & Audio Remux    |
+-------------------+      +-------------------+
```

### 2.1 Automated Drop Detection Script (Librosa)
This program parses audio, calculates the musical onset/RMS curve, and extracts the highest-energy drop window (default 30 seconds).

```python
import librosa
import numpy as np

def detect_peak_drop_window(audio_path, duration_limit=30.0):
    """
    Parses audio, standardizes the energy signal, and finds the 30-second window
    with the maximum average energy density (RMS).
    """
    # Load audio at low sample rate for speed
    y, sr = librosa.load(audio_path, sr=22050)
    
    # Calculate RMS energy envelope
    hop_length = 512
    rms = librosa.feature.rms(y=y, hop_length=hop_length)[0]
    times = librosa.frames_to_time(np.arange(len(rms)), sr=sr, hop_length=hop_length)
    
    # Scale RMS signal between 0 and 1
    rms_normalized = (rms - np.min(rms)) / (np.max(rms) - np.min(rms))
    
    # Find continuous segment exceeding high threshold (>0.8)
    # Slide a window of 30 seconds across the timeline to find the absolute maximum area
    window_frames = int(duration_limit * sr / hop_length)
    moving_avg = np.convolve(rms_normalized, np.ones(window_frames)/window_frames, mode='valid')
    
    max_idx = np.argmax(moving_avg)
    start_time = times[max_idx]
    end_time = start_time + duration_limit
    
    print(f"Detected Peak Drop Segment: Start {start_time:.2f}s, End {end_time:.2f}s (Average Energy Score: {moving_avg[max_idx]:.4f})")
    return start_time, end_time
```

### 2.2 CLI Demucs Separation & Pedalboard Mastering
Once the audio segment is extracted, the crowd bleed must be separated from the master track using Meta's Demucs CLI:

```bash
# Split high-fidelity audio from raw clip into stems
demucs --two-stems=vocals --mp3 -o /tmp/demucs_out /tmp/extracted_audio.wav
```
*Note: This isolates the live vocal/acoustic atmosphere in the "vocals" stem, leaving the heavy drums and electronic instrumentation isolated in the "no_vocals" stem for parallel mastering mixing.*

Next, apply the studio mastering DSP chain using Python's `pedalboard` API:
```python
from pedalboard import Pedalboard, HighpassFilter, Compressor, Limiter
from pedalboard.io import AudioFile

def master_audio_stems(input_audio_path, output_mastered_path):
    with AudioFile(input_audio_path) as f:
        audio = f.read(f.frames)
        sr = f.samplerate
        
    # Configure precise DSP mastering rack: low-cut rumble, tight compression, safe peak limit
    board = Pedalboard([
        HighpassFilter(cutoff_frequency_hz=40.0), # Eliminate sub-rumble below 40Hz
        Compressor(threshold_db=-16.0, ratio=4.0, attack_ms=10.0, release_ms=100.0),
        Limiter(threshold_db=-6.0, release_ms=100.0) # Set brickwall threshold
    ])
    
    effected = board(audio, sr)
    
    with AudioFile(output_mastered_path, 'w', sr, effected.shape[0]) as f:
        f.write(effected)
```

### 2.3 FFmpeg Auto-Reframe, Spatial Denoise & Export
The vertical reframing pipeline crops the 16:9 widescreen format into a 9:16 vertical standard (1080x1920) while applying high-performance spatial-temporal denoisers (`hqdn3d`) to remove concert camera noise.

```bash
# Auto-crop video to center 1080x1920, apply noise cleanup filters, and remux mastered audio stem
ffmpeg -i input_16_9.mp4 -i mastered_audio.wav -filter_complex \
  "[0:v]crop=ih*9/16:ih:icx:icy,hqdn3d=1.5:1.5:6:6,scale=1080:1920[v]" \
  -map "[v]" -map 1:a \
  -c:v libx264 -profile:v high -level 4.2 -pix_fmt yuv420p -r 60 -b:v 10M \
  -c:a aac -b:a 320k -shortest output_9_16_master.mp4
```

---

## Phase 3: Competitive Intelligence & SEO Scraper

This module coordinates headless scrapers that track competitor channel performance, extract metadata metrics, and push them to Google Sheets via the Sheets API v4.

### 3.1 Playwright Headless Channel Scraper
```python
import asyncio
from playwright.async_api import async_playwright

async def scrape_competitor_metrics(channel_url):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(channel_url)
        await page.wait_for_selector('ytd-rich-grid-row') # Ensure grid elements are loaded
        
        videos_data = []
        video_cards = await page.locator('ytd-rich-grid-media').all()
        
        for card in video_cards[:10]: # Parse top 10 recent uploads
            title = await card.locator('#video-title').text_content()
            views_str = await card.locator('#metadata-line span:nth-child(1)').text_content()
            link = await card.locator('a#thumbnail').get_attribute('href')
            
            # Clean view strings: "1.2M views" -> 1200000
            views = parse_views(views_str)
            videos_data.append({
                'title': title.strip(),
                'views': views,
                'link': f"https://youtube.com{link}"
            })
            
        await browser.close()
        return videos_data

def parse_views(views_str):
    if 'K' in views_str: return int(float(views_str.replace('K views', '').replace('K', '').strip()) * 1000)
    if 'M' in views_str: return int(float(views_str.replace('M views', '').replace('M', '').strip()) * 1000000)
    return int(re.sub(r'\D', '', views_str))
```

### 3.2 Sheets API Update Payload
This JSON payload structure represents a write request to append scraped trending metadata metrics directly to your planning spreadsheet:

```json
{
  "range": "Sheet1!A2:E",
  "valueInputOption": "USER_ENTERED",
  "data": [
    {
      "range": "Sheet1!A2:E",
      "values": [
        [
          "2026-08-21",
          "Laser Baptism Competition Peak",
          "https://youtube.com/shorts/XYZ_VideoLink",
          450000,
          "#lasers #edm #melodictechno"
        ]
      ]
    }
  ]
}
```

---

## Phase 4: Autonomous Publishing, Blogger & Copyright Shields

To prevent copyright claims while publishing and maintain platform optimization rules, the system deploys a two-tier mechanism: the **TikTok Ghost-Linking Remuxer** and the **YouTube Data API Unlisted Auditing Loop**.

### 4.1 TikTok Ghost-Linking Audio Remuxer (FFmpeg)
This command remuxes your vertical master file to contain the raw high-fidelity live venue master track on the left channel (or main sound mix) and merges the official commercial trending sound mapped directly on the secondary target track at 1% volume. This tricks TikTok's auto-muting algorithm into mapping the file as an official licensed sound, preventing copyright muting while maintaining 100% of your live audio energy.

```bash
# Merges main high-fidelity audio track at 100% and official sound library download at 1% volume
ffmpeg -i output_9_16_master.mp4 -i official_tiktok_commercial_track.mp3 -filter_complex \
  "[0:a]volume=1.0[a1];[1:a]volume=0.01[a2];[a1][a2]amix=inputs=2:duration=first[a_mix]" \
  -map 0:v -map "[a_mix]" -c:v copy -c:a aac -b:a 320k final_tiktok_ghost_linked.mp4
```

### 4.2 YouTube Data API v3 Unlisted Auditing Loop
This automation loops uploads to your channel with the initial publishing privacy setting configured to `unlisted`. It checks for algorithmic copyright claims or blocks for exactly one hour before shifting the file to `public` during optimized hours.

```python
import time

def upload_and_audit_short(service, filepath, title, description):
    # Prepare API Upload Payload
    body = {
        'snippet': {
            'title': title,
            'description': description,
            'categoryId': '10' # Music category
        },
        'status': {
            'privacyStatus': 'unlisted', # Force initial upload as Unlisted
            'selfDeclaredMadeForKids': False
        }
    }
    
    # Trigger multi-part chunked upload
    media = MediaFileUpload(filepath, chunksize=-1, resumable=True)
    request = service.videos().insert(part="snippet,status", body=body, media_body=media)
    video_response = request.execute()
    video_id = video_response['id']
    
    print(f"Short uploaded successfully as UNLISTED. Video ID: {video_id}")
    print("Initiating 1-Hour Copyright Scan Audit Loop...")
    
    audit_duration = 3600  # 1 Hour
    poll_interval = 300    # 5 Minutes
    elapsed = 0
    cleared = True
    
    while elapsed < audit_duration:
        time.sleep(poll_interval)
        elapsed += poll_interval
        
        # Check claim status via Data API
        status_req = service.videos().list(part="contentDetails,status", id=video_id)
        status_resp = status_req.execute()
        
        video_details = status_resp['files'][0]
        licensing = video_details.get('contentDetails', {}).get('licensingStatus', '')
        # Detect if Content ID has flagged or blocked the video globally
        if 'blocked' in licensing or 'claimed' in licensing:
            print(f"🚨 Copyright Claim/Block Detected! Status: {licensing}. Aborting publication.")
            cleared = False
            break
            
    if cleared:
        print("✅ Short passed 1-Hour Content ID audit scan with zero global blocks. Changing privacy to PUBLIC.")
        service.videos().update(
            part="status",
            body={
                "id": video_id,
                "status": {"privacyStatus": "public"}
            }
        ).execute()
```

### 4.3 Blogger API v3 Publishing Integration
This JSON schema maps the automated posting of companion blog posts that are launched in tandem with your short-form videos:

```json
{
  "kind": "blogger#post",
  "blog": {
    "id": "YOUR_BLOGGER_BLOG_ID"
  },
  "title": "Laser Baptism Live Drop: Melodic Techno Eclipse [RAW 60fps]",
  "content": "<p>Experience the ultimate high-fidelity laser sync capture from stadium house artist set. Sub-rumble mastered and processed via the Spark Orchestration Engine.</p><iframe src='https://www.youtube.com/embed/XYZ_VideoLink' width='360' height='640' frameborder='0' allowfullscreen></iframe>",
  "labels": [
    "Laser Baptism",
    "Melodic Techno",
    "Festival Live Drops"
  ]
}
```

---

## Technical Guardrails & Safe Zones (For IDE Validation UI rendering)
When generating overlays, captions, or custom graphics, Anti-Gravity must reference these hard coordinate matrices to avoid blocking UI elements on user phones:

| Platform | Canvas Aspect | Target Frame | Safe Area Top Exclusions | Safe Area Bottom Exclusions | Central Text Safe-Box |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **YouTube Shorts** | 9:16 vertical | 1080x1920 px | Y 0 – 180 px (Logo/Search) | Y 1450 – 1920 px (Description) | **900 x 1160 px** (Centered) |
| **TikTok** | 9:16 vertical | 1080x1920 px | Y 0 – 160 px (Follow/Tabs) | Y 1470 – 1920 px (Caption/Music) | **920 x 1250 px** (Centered) |

---

## Action Plan for Google Anti-Gravity IDE
1. **Provision Environment:** Create a Docker container or virtual environment pre-loading `ffmpeg`, `exiftool`, and Meta's `demucs` command-line modules.
2. **Setup OAuth Service Account:** Ingest a `credentials.json` with permissions activated for Google Drive API v3, Google Sheets API v4, Blogger API v3, and YouTube Data API v3.
3. **Execute Deployment:** 
   * Compile Phase 1 `routing_daemon.py` and register it with `systemd` to monitor the Drive storage folder.
   * Compile Phase 2 `audio_dsp_pipeline.py` and hook it to listen for file updates inside the `02_IN_PROGRESS` directory.
   * Run the Phase 3 Playwright automation daily to adjust SEO keyword triggers in your Sheet.
   * Attach the Phase 4 publishing loop to trigger the TikTok Ghost-Linking and YouTube automated public scheduler.
