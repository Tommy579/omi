import sys
import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path

# S'assurer que le dossier racine est dans le path
sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

class TestAssistantHardware(unittest.TestCase):
    @patch('core.assistant.genai.Client')
    @patch('core.assistant.cv2.VideoCapture')
    @patch('sounddevice.query_devices')
    def test_hardware_available(self, mock_query_devices, mock_video_capture, mock_genai_client):
        # Setup mock camera
        mock_camera = MagicMock()
        mock_camera.isOpened.return_value = True
        mock_video_capture.return_value = mock_camera

        # Setup mock sounddevice
        mock_query_devices.return_value = [
            {'name': 'Default Speaker', 'max_input_channels': 0},
            {'name': 'Default Microphone', 'max_input_channels': 1}
        ]

        from core.assistant import Assistant
        assistant = Assistant()

        self.assertTrue(assistant.is_camera_available)
        self.assertTrue(assistant.is_mic_available)
        self.assertIn("CAMÉRA DISPONIBLE", assistant._enhanced_prompt)
        self.assertIn("MICROPHONE DISPONIBLE", assistant._enhanced_prompt)
        self.assertNotIn("CAMÉRA NON DISPONIBLE", assistant._enhanced_prompt)
        self.assertNotIn("MICROPHONE NON DISPONIBLE", assistant._enhanced_prompt)

    @patch('core.assistant.genai.Client')
    @patch('core.assistant.cv2.VideoCapture')
    @patch('sounddevice.query_devices')
    def test_hardware_unavailable(self, mock_query_devices, mock_video_capture, mock_genai_client):
        # Setup mock camera failing to open
        mock_camera = MagicMock()
        mock_camera.isOpened.return_value = False
        mock_video_capture.return_value = mock_camera

        # Setup mock sounddevice with no input channels
        mock_query_devices.return_value = [
            {'name': 'Default Speaker', 'max_input_channels': 0}
        ]

        from core.assistant import Assistant
        assistant = Assistant()

        self.assertFalse(assistant.is_camera_available)
        self.assertFalse(assistant.is_mic_available)
        self.assertIn("CAMÉRA NON DISPONIBLE", assistant._enhanced_prompt)
        self.assertIn("MICROPHONE NON DISPONIBLE", assistant._enhanced_prompt)
        self.assertNotIn("CAMÉRA DISPONIBLE", assistant._enhanced_prompt)
        self.assertNotIn("MICROPHONE DISPONIBLE", assistant._enhanced_prompt)
