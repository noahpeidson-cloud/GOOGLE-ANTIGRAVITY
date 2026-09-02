import os
import json
import time
import logging
from pathlib import Path
from google import genai
from config import GEMINI_API_KEY, GEMINI_MODEL

logger = logging.getLogger("brain_link.gemini_tagger")
logging.basicConfig(level=logging.INFO)


def process_video_async(file_path: str, model_name: str | None = None) -> dict:
    """
    Process an uploaded video by dispatching it to Gemini API for asynchronous tagging and metadata extraction.
    Writes a JSON companion sidecar file '<file_path>.tags.json' upon completion.
    """
    path_obj = Path(file_path)
    if not path_obj.exists():
        logger.error(f"Video file not found for processing: {file_path}")
        return {"status": "error", "message": "File not found"}

    target_model = model_name or GEMINI_MODEL or "gemini-2.5-flash"
    tags_file = path_obj.with_suffix(f"{path_obj.suffix}.tags.json")

    logger.info(f"Starting background video tagging for: {file_path} using model {target_model}")

    try:
        # Initialize Google GenAI client
        api_key = GEMINI_API_KEY or os.getenv("GEMINI_API_KEY")
        if not api_key:
            client = genai.Client()
        else:
            client = genai.Client(api_key=api_key)

        logger.info(f"Uploading {file_path} to Gemini Files API...")
        video_file = client.files.upload(file=file_path)
        logger.info(f"Uploaded file name: {video_file.name}, state: {getattr(video_file, 'state', 'UNKNOWN')}")

        # Poll file state if processing is required
        poll_count = 0
        while getattr(video_file, "state", None) and str(video_file.state).upper() == "PROCESSING":
            time.sleep(2)
            poll_count += 1
            video_file = client.files.get(name=video_file.name)
            if poll_count > 60:
                raise TimeoutError("Gemini file processing timed out")

        prompt = (
            "Analyze this video and provide automated content tagging and metadata in JSON format with the following structure:\n"
            "{\n"
            '  "title": "Short descriptive title",\n'
            '  "summary": "1-2 sentence overview",\n'
            '  "tags": ["tag1", "tag2", "tag3"],\n'
            '  "detected_objects": ["object1", "object2"],\n'
            '  "key_moments": [{"timestamp": "00:00", "description": "..."}]\n'
            "}"
        )

        logger.info(f"Calling Gemini model {target_model} for tagging...")
        response = client.models.generate_content(
            model=target_model,
            contents=[video_file, prompt],
        )

        response_text = response.text or "{}"
        try:
            # Clean possible markdown code fences
            cleaned = response_text.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            parsed_metadata = json.loads(cleaned.strip())
        except Exception:
            parsed_metadata = {"raw_response": response_text, "tags": []}

        result_payload = {
            "status": "success",
            "file_path": str(path_obj),
            "model_used": target_model,
            "processed_at": time.time(),
            "metadata": parsed_metadata,
        }

        # Write sidecar JSON
        tags_file.write_text(json.dumps(result_payload, indent=2), encoding="utf-8")
        logger.info(f"Successfully processed and tagged video. Saved metadata to: {tags_file}")
        return result_payload

    except Exception as e:
        logger.error(f"Error processing video {file_path} with Gemini: {e}", exc_info=True)
        error_payload = {
            "status": "error",
            "file_path": str(path_obj),
            "error": str(e),
            "processed_at": time.time(),
        }
        try:
            tags_file.write_text(json.dumps(error_payload, indent=2), encoding="utf-8")
        except Exception:
            pass
        return error_payload
