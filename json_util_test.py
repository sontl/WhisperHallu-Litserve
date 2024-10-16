import unittest
from json_util import convert_gladia_to_internal_format

class TestConvertGladiaToInternalFormat(unittest.TestCase):
    def test_convert_gladia_to_internal_format(self):
        # Sample Gladia response
        gladia_response = {
            "result": {
                "full_transcript": "This is a test transcript.",
                "transcription": {
                    "utterances": [
                        {
                            "start": 0.0,
                            "end": 2.5,
                            "text": "This is a test",
                            "words": [
                                {"start": 0.0, "end": 0.5, "word": "This"},
                                {"start": 0.6, "end": 0.9, "word": "is"},
                                {"start": 1.0, "end": 1.2, "word": "a"},
                                {"start": 1.3, "end": 2.5, "word": "test"}
                            ]
                        },
                        {
                            "start": 2.6,
                            "end": 3.5,
                            "text": "transcript.",
                            "words": [
                                {"start": 2.6, "end": 3.5, "word": "transcript."}
                            ]
                        }
                    ]
                }
            }
        }

        # Expected output
        expected_output = {
            "text": "This is a test transcript.",
            "srt": "",
            "json": [
                {
                    "start": 0.0,
                    "end": 2.5,
                    "sentence": "This is a test",
                    "words": [
                        {"start": 0.0, "end": 0.5, "text": "This"},
                        {"start": 0.6, "end": 0.9, "text": "is"},
                        {"start": 1.0, "end": 1.2, "text": "a"},
                        {"start": 1.3, "end": 2.5, "text": "test"}
                    ]
                },
                {
                    "start": 2.6,
                    "end": 3.5,
                    "sentence": "transcript.",
                    "words": [
                        {"start": 2.6, "end": 3.5, "text": "transcript."}
                    ]
                }
            ]
        }

        # Call the function
        result = convert_gladia_to_internal_format(gladia_response)

        # Assert the result
        self.assertEqual(result, expected_output)

if __name__ == '__main__':
    unittest.main()
