import unittest
from unittest.mock import patch, mock_open
import os
import shutil
import logging
from ib_cicd.promote_solution import (
    copy_solution_to_working_dir,
    upload_zip_to_instabase,
    version_tuple,
    get_latest_binary_path,
    parse_dependencies,
)


class TestPromoteSolution(unittest.TestCase):
    @patch("ib_cicd.promote_solution.copy_file_within_ib")
    def test_copy_solution_to_working_dir(self, mock_copy):
        copy_solution_to_working_dir("host", "token", "/source", "flow/path", "/new")
        self.assertEqual(mock_copy.call_count, 2)

    @patch("ib_cicd.promote_solution.upload_file")
    @patch("builtins.open", new_callable=mock_open, read_data=b"data")
    @patch("shutil.make_archive")
    def test_upload_zip_to_instabase(self, mock_archive, mock_open, mock_upload):
        mock_upload.return_value = "Success"
        result = upload_zip_to_instabase("/target", "host", "token", "solution")
        mock_archive.assert_called_once()
        mock_open.assert_called_once_with("solution.zip", "rb")
        mock_upload.assert_called_once()
        self.assertEqual(result, "Success")

    def test_version_tuple(self):
        self.assertEqual(version_tuple("1.2.3"), (1, 2, 3))
        self.assertEqual(version_tuple("0.0.1"), (0, 0, 1))

    @patch("ib_cicd.promote_solution.list_directory")
    def test_get_latest_binary_path(self, mock_list):
        mock_list.return_value = ["/path/1.2.3.ibflowbin", "/path/2.0.0.ibflowbin"]
        result = get_latest_binary_path("token", "host", "/solution")
        self.assertEqual(result, "/path/2.0.0.ibflowbin")

    def test_parse_dependencies(self):
        self.assertEqual(
            parse_dependencies(["pkg1==1.0", "pkg2==2.1"]),
            {"pkg1": "1.0", "pkg2": "2.1"},
        )
        self.assertEqual(parse_dependencies([]), {})
        self.assertEqual(parse_dependencies(["invalid"]), {})


if __name__ == "__main__":
    unittest.main()
