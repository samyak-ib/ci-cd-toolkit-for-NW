import unittest
from unittest.mock import patch, mock_open, MagicMock
import json
from ib_cicd.promote_build_solution import (
    download_file,
    save_to_file,
)


class TestPromoteBuildSolution(unittest.TestCase):
    @patch("ib_cicd.promote_build_solution.read_file_through_api")
    @patch("builtins.open", new_callable=mock_open)
    def test_download_file(self, mock_file, mock_api):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = json.dumps({"key": "value"}).encode("utf-8")
        mock_api.return_value = mock_response

        result = download_file("http://example.com", "token", "solution/path")
        self.assertEqual(json.loads(result), {"key": "value"})
        mock_file.assert_called_once_with("path", "w")

    @patch("builtins.open", new_callable=mock_open)
    def test_save_to_file(self, mock_file):
        save_to_file({"key": "value"}, "test.json")
        mock_file.assert_called_once_with("test.json", "w")


if __name__ == "__main__":
    unittest.main()
