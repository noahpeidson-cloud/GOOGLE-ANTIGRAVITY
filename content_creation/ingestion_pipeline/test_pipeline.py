import unittest
from unittest.mock import patch

# The implementation module does not exist yet.
from pipeline import process_video, trigger_cloud_run

class TestVideoIngestionPipeline(unittest.TestCase):
    def test_process_video_called_with_correct_args(self):
        video_path = "/mock/syncthing/incoming/8k_video.mp4"
        
        with patch('pipeline.upload_to_gcs') as mock_upload:
            process_video(video_path)
            mock_upload.assert_called_once_with(video_path)
            
    def test_trigger_cloud_run_pubsub(self):
        video_id = "vid_12345"
        
        with patch('pipeline.publish_pubsub_message') as mock_publish:
            trigger_cloud_run(video_id)
            mock_publish.assert_called_once_with('video-ingestion-topic', b'{"video_id": "vid_12345"}')

if __name__ == '__main__':
    unittest.main()
