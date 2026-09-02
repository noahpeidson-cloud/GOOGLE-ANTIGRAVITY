# Brain Link - FastAPI Backend

High-performance FastAPI video ingestion backend for the **Brain Link** ecosystem.

## Features

1. **Pairing & QR Code Generator**:
   - `GET /api/pair-info`: Returns local network IP, server port, upload endpoint, and active Auth Token.
   - `GET /api/qr`: Dynamically generates and serves PNG pairing QR code for zero-friction mobile pairing.
   - `python qr_generator.py`: CLI command to print pairing info and ASCII QR code directly in the terminal.

2. **Secure 1GB+ 4K Video Ingestion**:
   - `POST /api/upload`: Authenticated endpoint (validates `Authorization: Bearer <TOKEN>` or `X-Auth-Token: <TOKEN>`).
   - Streams 1MB binary chunks directly to disk (`uploads/`), avoiding memory exhaustion during multi-gigabyte 4K video uploads.
   - Returns `HTTP 200 OK` immediately upon stream write completion.

3. **Asynchronous Gemini Tagging**:
   - Dispatches a background task (`process_video_async`) to ingest the uploaded video to Google GenAI (`gemini-omni-flash` / `gemini-2.5-flash`).
   - Generates and saves structured content metadata (tags, title, summary, key moments) into a companion JSON file (`<video_filename>.tags.json`).

## Architecture & File Structure

```
brain_link/backend/
├── config.py             # Environment configuration & token management
├── qr_generator.py       # Local IP discovery & QR code generator (CLI + API helper)
├── gemini_tagger.py      # Background worker for Google GenAI video tagging
├── main.py               # FastAPI application & upload streaming endpoints
├── requirements.txt      # Python dependencies
├── README.md             # Architecture and usage documentation
└── tests/
    └── test_backend.py   # Deterministic pytest suite (Loud Assertions)
```

## Running the Server

```bash
python main.py
```
Or with uvicorn:
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

## Running the QR Pairing CLI

```bash
python qr_generator.py
```

## Running the Test Suite

```bash
python -m pytest tests/test_backend.py -v
```
