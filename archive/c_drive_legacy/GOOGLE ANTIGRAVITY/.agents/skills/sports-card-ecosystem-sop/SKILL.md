---
name: sports-card-ecosystem-sop
description: SOP for booting and operating the Sports Card Ecosystem Hub (Streamlit UI, FastAPI Chrome Extension Bridge, and BigQuery Export).
---

# SOP: Sports Card Ecosystem Hub

## Overview
The Sports Card Ecosystem is the central staging area for processing raw card data from Facebook Marketplace, Beckett Checklists, and AI Vision analysis, before pushing it to Card Ladder.

**Location:** `g:\My Drive\GOOGLE ANTIGRAVITY\sports_cards\ecosystem_hub`

## Step-by-Step Boot Sequence

### 1. Zero-Friction Boot
The entire ecosystem (FastAPI Backend + Streamlit Frontend) is orchestrated by a single boot script.
1. Navigate to the project directory: `cd g:\My Drive\GOOGLE ANTIGRAVITY\sports_cards\ecosystem_hub`
2. Run the launcher: `python boot_hub.py`
3. The script will automatically launch the backend, frontend, and open your browser to `http://localhost:8501`.

### 2. Execution & Export
- **Ingestion:** Data is automatically ingested into the local `portfolio.db` SQLite database when the Chrome Extension hits the FastAPI endpoint on port 8000.
- **Exporting:** To export to Card Ladder, click the "Export to CSV" button in the Streamlit UI. This triggers `export.py` which scrubs the data (preserving leading zeros) and generates `CardLadder_Bulk_Upload.csv`.
