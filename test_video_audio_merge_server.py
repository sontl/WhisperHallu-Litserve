import unittest
from unittest.mock import patch, MagicMock
import tempfile
import os
from fastapi import HTTPException
from video_audio_merge_server import VideoAudioMergeAPI

class TestVideoAudioMergeAPI(unittest.TestCase):

    def setUp(self):
        self.api = VideoAudioMergeAPI()

    @patch('video_audio_merge_server.tempfile.NamedTemporaryFile')
    @patch('video_audio_merge_server.urllib.request.urlretrieve')
    def test_decode_request_success(self, mock_urlretrieve, mock_temp_file):
        # Mock request data
        mock_request = {
            "video": MagicMock(file=MagicMock(read=lambda: b"video_content")),
            "audio_url": "http://example.com/audio.mp3"
        }

        # Mock temporary files
        mock_video_temp = MagicMock(name='/tmp/video.mp4')
        mock_audio_temp = MagicMock(name='/tmp/audio.mp3')
        mock_temp_file.side_effect = [mock_video_temp, mock_audio_temp]

        result = self.api.decode_request(mock_request)

        self.assertEqual(result, (mock_video_temp.name, mock_audio_temp.name))
        mock_urlretrieve.assert_called_once_with("http://example.com/audio.mp3", mock_audio_temp.name)

    def test_decode_request_no_video(self):
        mock_request = {"audio_url": "http://example.com/audio.mp3"}
        with self.assertRaises(HTTPException) as context:
            self.api.decode_request(mock_request)
        self.assertEqual(context.exception.status_code, 400)
        self.assertEqual(context.exception.detail, "No video file found in the request.")

    def test_decode_request_no_audio_url(self):
        mock_request = {"video": MagicMock(file=MagicMock(read=lambda: b"video_content"))}
        with self.assertRaises(HTTPException) as context:
            self.api.decode_request(mock_request)
        self.assertEqual(context.exception.status_code, 400)
        self.assertEqual(context.exception.detail, "No audio URL provided in the request.")

    @patch('video_audio_merge_server.subprocess.run')
    def test_predict_success(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        
        with tempfile.NamedTemporaryFile(suffix='.mp4') as video_temp, \
             tempfile.NamedTemporaryFile(suffix='.mp3') as audio_temp:
            
            result = self.api.predict((video_temp.name, audio_temp.name))
            
            self.assertTrue(os.path.exists(result))
            self.assertTrue(result.endswith('.mp4'))
            mock_run.assert_called_once()

    @patch('video_audio_merge_server.subprocess.run')
    def test_predict_ffmpeg_error(self, mock_run):
        mock_run.side_effect = subprocess.CalledProcessError(1, 'ffmpeg', stderr=b"FFmpeg error")
        
        with tempfile.NamedTemporaryFile(suffix='.mp4') as video_temp, \
             tempfile.NamedTemporaryFile(suffix='.mp3') as audio_temp:
            
            with self.assertRaises(HTTPException) as context:
                self.api.predict((video_temp.name, audio_temp.name))
            
            self.assertEqual(context.exception.status_code, 500)
            self.assertTrue("FFmpeg error" in context.exception.detail)

    def test_encode_response_success(self):
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_file:
            temp_file.write(b"test content")
            temp_file.close()
            
            response = self.api.encode_response(temp_file.name)
            
            self.assertEqual(response.body, b"test content")
            self.assertEqual(response.media_type, "video/mp4")
            self.assertFalse(os.path.exists(temp_file.name))

    def test_encode_response_file_not_found(self):
        with self.assertRaises(HTTPException) as context:
            self.api.encode_response("non_existent_file.mp4")
        
        self.assertEqual(context.exception.status_code, 500)
        self.assertTrue("Error encoding response" in context.exception.detail)

if __name__ == '__main__':
    unittest.main()
