import os
import sys
import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path
import tempfile

# S'assurer que le dossier racine est dans le path
sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from core.tools import (
    list_directory,
    read_file,
    write_file,
    get_active_app_name,
    send_message_with_retry
)

class TestTools(unittest.TestCase):
    def test_list_directory_valid(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            res = list_directory(tmpdir)
            self.assertIn("items", res)
            self.assertIn("current_path", res)
            self.assertEqual(res["items"], [])

    def test_list_directory_invalid(self):
        res = list_directory("/non_existent_directory_xyz_123")
        self.assertIn("error", res)

    def test_write_and_read_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "test.txt")
            # Simuler USERPROFILE pour que write_file autorise l'écriture sans force=True
            with patch.dict(os.environ, {"USERPROFILE": tmpdir}):
                write_res = write_file(test_file, "hello world")
                self.assertIn("status", write_res)
                
                read_res = read_file(test_file)
                self.assertEqual(read_res.get("content"), "hello world")

    def test_write_file_outside_profile_without_force(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "test.txt")
            with patch.dict(os.environ, {"USERPROFILE": "/different/path"}):
                write_res = write_file(test_file, "hello")
                self.assertIn("error", write_res)
                self.assertIn("Écriture refusée", write_res["error"])

    def test_write_file_outside_profile_with_force(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "test.txt")
            with patch.dict(os.environ, {"USERPROFILE": "/different/path"}):
                write_res = write_file(test_file, "hello", force=True)
                self.assertIn("status", write_res)
                read_res = read_file(test_file)
                self.assertEqual(read_res.get("content"), "hello")

    @patch('psutil.Process')
    def test_get_active_app_name_linux(self, mock_process):
        with patch('os.name', 'posix'):
            with patch('subprocess.check_output') as mock_check_output:
                mock_check_output.return_value = b" 12345 \n"
                mock_proc_instance = MagicMock()
                mock_proc_instance.name.return_value = "my_test_app"
                mock_process.return_value = mock_proc_instance
                
                app_name = get_active_app_name()
                self.assertEqual(app_name, "my_test_app")
                mock_check_output.assert_called()

    def test_send_message_with_retry_success(self):
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "Hello back"
        mock_session.send_message.return_value = mock_response
        
        res = send_message_with_retry(mock_session, "Hi")
        self.assertEqual(res, mock_response)
        mock_session.send_message.assert_called_once_with("Hi")

    @patch('time.sleep')
    def test_send_message_with_retry_quota_error(self, mock_sleep):
        mock_session = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "Success after retry"
        mock_session.send_message.side_effect = [Exception("Resource exhausted (429)"), mock_response]
        
        res = send_message_with_retry(mock_session, "Hi", max_retries=3)
        self.assertEqual(res, mock_response)
        self.assertEqual(mock_session.send_message.call_count, 2)
        mock_sleep.assert_called_once_with(1.0)

    @patch('time.sleep')
    def test_send_message_with_retry_max_retries_reached(self, mock_sleep):
        mock_session = MagicMock()
        mock_session.send_message.side_effect = Exception("Resource exhausted (429)")
        
        with self.assertRaises(Exception) as context:
            send_message_with_retry(mock_session, "Hi", max_retries=3)
            
        self.assertIn("429", str(context.exception))
        self.assertEqual(mock_session.send_message.call_count, 3)
