import unittest
from unittest.mock import patch
import json
from transcribeHallu import transcribe_with_gladia

class TestTranscribeWithGladia(unittest.TestCase):

    @patch('transcribeHallu.requests.post')
    @patch('transcribeHallu.requests.get')
    def test_successful_transcription(self, mock_get, mock_post):
        # Mock the API responses
        mock_post.side_effect = [
            unittest.mock.Mock(status_code=200, json=lambda: {"audio_url": "http://example.com/audio"}),
            unittest.mock.Mock(status_code=200, json=lambda: {"result_url": "http://example.com/result"})
        ]
        mock_get.return_value = unittest.mock.Mock(status_code=200, json=lambda: {
            "transcription": {"full_transcript": "Test transcript"},
            "translation": {"full_transcript": "Test translation"},
            "subtitles": {"srt": "1\n00:00:00,000 --> 00:00:05,000\nTest subtitle"}
        })

        result = transcribe_with_gladia("test.mp3", "en", "en")
        result_dict = json.loads(result)

        self.assertIn("text", result_dict)
        self.assertIn("srt", result_dict)
        self.assertIn("json", result_dict)
        self.assertEqual(result_dict["text"], "Test translation")

    @patch('transcribeHallu.requests.post')
    def test_upload_failure(self, mock_post):
        mock_post.return_value = unittest.mock.Mock(status_code=400, text="Upload failed")

        result = transcribe_with_gladia("test.mp3", "en", "en")
        result_dict = json.loads(result)

        self.assertEqual(result_dict, {"text": "", "srt": "", "json": []})

    # Add more test cases for different scenarios

if __name__ == '__main__':
    unittest.main()

