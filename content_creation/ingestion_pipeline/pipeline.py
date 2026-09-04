from google.cloud import storage
from google.cloud import pubsub_v1
import json

def upload_to_gcs(video_path):
    client = storage.Client()
    # Placeholder bucket implementation
    bucket = client.bucket("video-ingestion-bucket")
    filename = video_path.split("/")[-1]
    blob = bucket.blob(f"incoming/{filename}")
    blob.upload_from_filename(video_path)

def publish_pubsub_message(topic, message_bytes):
    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path("project-id", topic)
    publisher.publish(topic_path, message_bytes)

def process_video(video_path):
    upload_to_gcs(video_path)

def trigger_cloud_run(video_id):
    message_data = {"video_id": video_id}
    # Using separators=(',', ': ') to match the exact string in the test if needed, though default json.dumps might be fine.
    # The test expects: b'{"video_id": "vid_12345"}'
    message_bytes = json.dumps(message_data).encode("utf-8")
    publish_pubsub_message('video-ingestion-topic', message_bytes)
