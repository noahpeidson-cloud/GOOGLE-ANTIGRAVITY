import os
import shutil
import logging
from pathlib import Path
from fastapi import FastAPI, File, UploadFile, Header, HTTPException, BackgroundTasks, Depends, Response
from fastapi.responses import JSONResponse
from config import AUTH_TOKEN, UPLOAD_DIR, SERVER_HOST, SERVER_PORT
from qr_generator import get_local_ip, get_pairing_payload, generate_qr_image_bytes
from gemini_tagger import process_video_async

logger = logging.getLogger("brain_link.main")
logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="Brain Link Video Ingestion Server",
    description="High-performance FastAPI server for 4K video ingestion, device pairing, and async Gemini tagging.",
    version="1.0.0",
)


def verify_auth_token(
    authorization: str | None = Header(None, alias="Authorization"),
    x_auth_token: str | None = Header(None, alias="X-Auth-Token"),
) -> str:
    """Validate Bearer token or X-Auth-Token against server AUTH_TOKEN."""
    token = None
    if authorization:
        if authorization.startswith("Bearer "):
            token = authorization.split("Bearer ", 1)[1].strip()
        else:
            token = authorization.strip()
    elif x_auth_token:
        token = x_auth_token.strip()

    if not token or token != AUTH_TOKEN:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token


@app.get("/")
def root():
    return {
        "service": "Brain Link Backend",
        "status": "online",
        "version": "1.0.0",
    }


@app.get("/health")
@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "upload_dir": UPLOAD_DIR,
        "upload_dir_exists": os.path.exists(UPLOAD_DIR),
    }


@app.get("/api/pair-info")
def get_pair_info():
    """Returns connection information including server local IP, port, and auth token."""
    return get_pairing_payload()


@app.get("/api/qr")
def get_qr_code():
    """Generates and serves pairing QR code as PNG image."""
    payload = get_pairing_payload()
    qr_png_bytes = generate_qr_image_bytes(payload)
    return Response(content=qr_png_bytes, media_type="image/png")


@app.post("/api/upload")
async def upload_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    auth: str = Depends(verify_auth_token),
):
    """
    Accepts 1GB+ 4K video uploads via chunked stream, writes immediately to disk,
    returns HTTP 200, and dispatches background Gemini tagging.
    """
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    filename = Path(file.filename or "uploaded_video.mp4").name
    destination_path = Path(UPLOAD_DIR) / filename

    # Prevent overwriting existing file with identical name by suffixing timestamp if needed
    if destination_path.exists():
        stem = destination_path.stem
        suffix = destination_path.suffix
        counter = 1
        while destination_path.exists():
            destination_path = Path(UPLOAD_DIR) / f"{stem}_{counter}{suffix}"
            counter += 1

    logger.info(f"Receiving streaming upload: {filename} -> {destination_path}")

    # Stream write in 1MB chunks to handle 1GB+ files without memory bloat
    chunk_size = 1024 * 1024  # 1MB
    total_bytes = 0

    try:
        with open(destination_path, "wb") as buffer:
            while chunk := await file.read(chunk_size):
                buffer.write(chunk)
                total_bytes += len(chunk)
    except Exception as e:
        logger.error(f"Failed writing upload stream to disk: {e}", exc_info=True)
        if destination_path.exists():
            try:
                destination_path.unlink()
            except Exception:
                pass
        raise HTTPException(status_code=500, detail=f"Failed writing file: {str(e)}")
    finally:
        await file.close()

    logger.info(f"Completed streaming write for {destination_path} ({total_bytes} bytes). Dispatching background tagging task.")

    # Dispatch asynchronous Gemini tagging background task
    background_tasks.add_task(process_video_async, str(destination_path))

    return JSONResponse(
        status_code=200,
        content={
            "status": "success",
            "message": "File uploaded successfully. Background tagging initiated.",
            "file_name": destination_path.name,
            "saved_path": str(destination_path),
            "file_size_bytes": total_bytes,
        },
    )


if __name__ == "__main__":
    import uvicorn
    print(f"Starting Brain Link FastAPI Server on {SERVER_HOST}:{SERVER_PORT}...")
    uvicorn.run("main:app", host=SERVER_HOST, port=SERVER_PORT, reload=True)
