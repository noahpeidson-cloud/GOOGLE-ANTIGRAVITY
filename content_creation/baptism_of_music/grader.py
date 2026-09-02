import os
import sqlite3
import datetime
import logging
from google import genai
from google.genai import types

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

DB_PATH = os.path.join(os.path.dirname(__file__), "trends.db")

# Initialize GenAI Client
# Ensure GEMINI_API_KEY is set in the environment
client = genai.Client()

def get_current_trends():
    """Retrieve the active trends from the local SQLite context."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # We only care about trends that survived the garbage collection
    cursor.execute("SELECT trend_name, tags FROM viral_trends")
    trends = cursor.fetchall()
    conn.close()
    
    return trends

def grade_video(video_path: str):
    """
    Uploads a video to Gemini and asks it to grade the video against current viral trends.
    This executes the 'Advisory Mode' protocol.
    """
    logging.info(f"Uploading video for grading: {video_path}")
    
    # Check if file exists
    if not os.path.exists(video_path):
        logging.error(f"File not found: {video_path}")
        return
        
    try:
        # Upload the file using the standard GenAI Files API
        video_file = client.files.upload(file=video_path)
        logging.info(f"Upload complete. File URI: {video_file.uri}")
        
        # Retrieve context
        current_trends = get_current_trends()
        trend_context = "Current Active Trends Context:\\n"
        for t in current_trends:
            trend_context += f"- {t[0]} (Tags: {t[1]})\\n"
            
        prompt = f"""
        {trend_context}
        
        You are an expert EDM Media Curator and Viral Trend Analyst.
        Watch this video and grade it for 'Viral Potential' on a scale of 1-100 based on the current trends context provided above.
        
        Output your response as JSON matching this schema:
        {{
            "viral_potential_score": int,
            "feedback_notes": "A short paragraph explaining the score and what edits (cuts, lighting, hooks) could improve it."
        }}
        """
        
        logging.info("Analyzing video with Gemini 1.5 Pro...")
        response = client.models.generate_content(
            model='gemini-1.5-pro',
            contents=[video_file, prompt],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            ),
        )
        
        # Clean up file after analysis
        client.files.delete(name=video_file.name)
        
        # Parse result and store in Advisory Mode (PENDING_APPROVAL)
        import json
        result = json.loads(response.text)
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO video_grades (video_filename, viral_potential_score, feedback_notes, date_graded, status)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            os.path.basename(video_path), 
            result.get('viral_potential_score', 0), 
            result.get('feedback_notes', ''), 
            datetime.date.today().isoformat(),
            'PENDING_APPROVAL'
        ))
        conn.commit()
        conn.close()
        
        logging.info(f"Grading Complete! Score: {result.get('viral_potential_score')}/100. Status: PENDING_APPROVAL")
        print(f"\\n--- ADVISORY REPORT ---")
        print(f"Score: {result.get('viral_potential_score')}/100")
        print(f"Feedback: {result.get('feedback_notes')}\\n")
        
    except Exception as e:
        logging.error(f"Error during video grading: {e}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        grade_video(sys.argv[1])
    else:
        print("Usage: python grader.py <path_to_video.mp4>")
