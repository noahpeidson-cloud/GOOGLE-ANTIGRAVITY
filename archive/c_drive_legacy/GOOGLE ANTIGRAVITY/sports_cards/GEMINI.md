# [HOBBY] Sports Cards Domain Rules & Ingestion Schema

<system>
## Operational Scope & Domain Context
This directory (`/sports_cards`) contains the data pipelines, ETL automation, relational key architecture, and analytics for Noah Eidson's Sports Cards hobby track.
All code and workflows executed within this directory MUST adhere strictly to the relational schemas, category enumerations, and tooling constraints defined below.
</system>

## Relational Key Architecture (Strict Enforcement)
- **Parent Image ID:** 4-digit integer per physical photo file (e.g., `8492`). MUST NEVER BE RECYCLED.
- **Child Card ID:** 3-digit suffix per distinct card (e.g., `8492-105`).
- **Tracking Field:** `[Parent_Image_ID]-[Child_Card_ID]` written to Column 15 (`Notes`).
- **File Naming Convention:** `CardScan-[YYYYMMDD]-[Parent_Image_ID].jpg`.

## The 21-Variable Ingestion Schema
Agents and scripts are STRICTLY FORBIDDEN from deviating from this structure, adding columns, dropping columns, or inventing categories:
1. **Date Purchased**: `MM/DD/YYYY` (Default to today's date)
2. **Quantity**: `1`
3. **Player**: Full athlete name or TCG character name
4. **Year**: 4-digit `YYYY`
5. **Set**: Manufacturer and release line (e.g., `Panini Prizm`, `Topps Chrome`)
6. **Variation**: Aggressively guess visual foil/sheen/parallel (e.g., `Silver Prizm`, `Refractor`). Leave blank ONLY for verified base cards.
7. **Number**: Printed card number (e.g., `#24`, `RC-1`)
8. **Category**: MUST match one of the 22 exact permitted categories:
   `[Basketball, Baseball, Football, Hockey, Soccer, Tennis, Wrestling, Racing, Golf, Boxing, UFC/MMA, Pokemon, Magic, Metazoo, Yugioh, Fortnite, Dragonballz, Entertainment, Swimming, Softball, PopCulture, Flesh and Blood]`
9. **Condition**: MUST BE EXACTLY `'Raw'` for ungraded cards. For graded cards, use syntax without hyphens (e.g., `PSA 10`, `BGS 9.5`, `SGC 10`, `CGC 9.5`).
10. **Slab Serial #**: Graded certification number string (MUST be Blank if Raw).
11. **Investment**: `0.00` (float with 2 decimal places).
12. **Estimated Value**: OCR Last Sold price or `0.00`.
13. **Ladder ID**: Blank (reserved for Card Ladder sync).
14. **Query**: `[Year] [Set] [Player] [Variation] [Condition]`. Negative exclusions (`-BGS -SGC`) are FORBIDDEN on `'Raw'` cards.
15. **Notes**: `[Parent_Image_ID]-[Child_Card_ID]` (e.g., `8492-105`).
16. **Tags**: Blank.
17. **Date Sold**: Blank.
18. **Sold Price**: Blank.
19. **Image**: Direct Google Drive URL.
20. **Back Image**: Direct Google Drive URL or blank.
21. **AI Status**: MUST be one of: `REVIEW VARIATION`, `NEEDS REVIEW`, or `CLEARED`. Any card with a visually guessed variation MUST be flagged `REVIEW VARIATION`.

## 500-Card Batch Circuit Breaker
- **Staging Limit:** Halt processing if the staging dataset or CSV batch reaches 500 rows.
- **Action:** Trigger automated batch export, SQLite commit, and staging table rollover before accepting further cards.

## Evasive Capture & Data Ingestion (Anti-Bot Protocol)
- **STRICTLY PROHIBITED:** Agents must NEVER attempt to autonomously scrape heavily defended secondary markets (eBay, Card Ladder, PWCC) using `chrome-devtools` or Puppeteer, as this triggers Cloudflare/Datadome bans.
- **The Evasive Workflow:** All web ingestion must rely on the user manually browsing the site and clicking the `zero_friction_capture_extension`. 
- **Agent's Role:** The agent acts as the ETL Watchdog. It monitors the local `inbox.db` populated by the extension, extracts the raw records, enforces the strict 21-variable schema, and compiles them into a `CardLadder_Bulk_Upload.csv` for final ingestion.

## Approved Tooling & Stack
- `pandas`: Dataframe transformations and CSV serialization.
- `sqlite3`: Relational database operations and transactional batch commits.
- `openpyxl` / standard Python libraries for file management.

## Domain Isolation & Forbidden Tools
- **STRICTLY PROHIBITED:** FFmpeg, media encoding, video filters (`hqdn3d`, `nlmeans`), audio loudness normalization (`loudnorm`), video transcoding, or any content creation tools.
- Any request to apply media engineering or video processing within `/sports_cards` MUST be rejected with a domain mismatch error.
