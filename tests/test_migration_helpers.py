import unittest
from unittest.mock import patch, MagicMock
import os
from ib_cicd.migration_helpers import (
    download_solution,
    copy_package_from_marketplace,
    check_if_file_exists_on_ib_env,
    copy_marketplace_package_and_move_to_new_env,
    download_dependencies_from_dev_and_upload_to_prod,
    publish_dependencies,
)


class TestMigrationHelpers(unittest.TestCase):
    @patch("ib_cicd.migration_helpers.read_file_through_api")
    @patch("builtins.open", new_callable=unittest.mock.mock_open)
    @patch("ib_cicd.migration_helpers.ZipFile")
    @patch("os.remove")
    def test_download_solution(
        self, mock_remove, mock_zipfile, mock_open, mock_read_api
    ):
        mock_resp = MagicMock()
        mock_resp.content = b"dummy_content"
        mock_read_api.return_value = mock_resp

        response = download_solution("host", "token", "path")

        self.assertEqual(response, mock_resp)
        mock_open.assert_called()
        mock_zipfile.assert_called()
        mock_remove.assert_called()

    @patch("ib_cicd.migration_helpers.requests.post")
    @patch("ib_cicd.migration_helpers.wait_until_job_finishes")
    def test_copy_package_from_marketplace(self, mock_wait, mock_post):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"job_id": "1234"}
        mock_post.return_value = mock_resp

        result = copy_package_from_marketplace(
            "host", "token", "package", "1.0", "path"
        )

        self.assertEqual(result, "path/package-1.0.ibsolution")
        mock_wait.assert_called()

    @patch("ib_cicd.migration_helpers.get_file_metadata")
    def test_check_if_file_exists_on_ib_env(self, mock_metadata):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"Content-Length": "100001"}
        mock_metadata.return_value = mock_response

        result = check_if_file_exists_on_ib_env("host", "token", "path")
        self.assertTrue(result)

        mock_response.headers = {"Content-Length": "99999"}
        result = check_if_file_exists_on_ib_env("host", "token", "path")
        self.assertFalse(result)

    @patch("ib_cicd.migration_helpers.upload_chunks")
    @patch("ib_cicd.migration_helpers.read_file_content_from_ib")
    @patch("ib_cicd.migration_helpers.copy_package_from_marketplace")
    @patch("ib_cicd.migration_helpers.check_if_file_exists_on_ib_env")
    @patch("ib_cicd.migration_helpers.get_file_metadata")
    def test_copy_marketplace_package_and_move_to_new_env(
        self,
        mock_metadata,
        mock_check_file,
        mock_copy_package,
        mock_read_file,
        mock_upload,
    ):
        mock_metadata.return_value.status_code = 404
        mock_check_file.return_value = False
        mock_read_file.return_value = b"file_contents"
        mock_upload.return_value = "upload_response"

        resp, path = copy_marketplace_package_and_move_to_new_env(
            "src_host",
            "tgt_host",
            "pkg",
            "1.0",
            "src_token",
            "tgt_token",
            "dwn_folder",
            "upload_folder",
        )

        self.assertEqual(path, "upload_folder/pkg-1.0.ibsolution")
        self.assertEqual(resp, "upload_response")

    @patch("ib_cicd.migration_helpers.create_folder_if_it_does_not_exists")
    @patch("ib_cicd.migration_helpers.copy_marketplace_package_and_move_to_new_env")
    def test_download_dependencies_from_dev_and_upload_to_prod(
        self, mock_copy_package, mock_create_folder
    ):
        mock_copy_package.side_effect = [(None, "path1"), (None, "path2")]
        dependency_dict = {"pkg1": "1.0", "pkg2": "2.0"}

        result = download_dependencies_from_dev_and_upload_to_prod(
            "src_host",
            "tgt_host",
            "src_token",
            "tgt_token",
            "dwn_folder",
            "upload_folder",
            dependency_dict,
        )

        self.assertEqual(result, ["path1", "path2"])

    @patch("ib_cicd.migration_helpers.publish_to_marketplace")
    def test_publish_dependencies(self, mock_publish):
        mock_publish.return_value = "Success"

        publish_dependencies(["path1", "path2"], "host", "token")

        mock_publish.assert_called()


if __name__ == "__main__":
    unittest.main()
