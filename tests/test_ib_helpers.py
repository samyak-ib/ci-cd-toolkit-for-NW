import json
import unittest
from unittest.mock import patch, Mock, MagicMock
import requests

from ib_cicd.ib_helpers import (
    upload_chunks,
    upload_file,
    read_file_through_api,
    publish_to_marketplace,
    make_api_request,
    check_job_status,
    check_job_status_build,
    unzip_files,
    compile_solution,
    copy_file_within_ib,
    create_folder_if_it_does_not_exists,
    list_directory,
    get_file_metadata,
    delete_folder_or_file_from_ib,
    generate_flow,
    read_file_content_from_ib,
    wait_until_job_finishes,
    delete_app,
    get_app_details,
    get_deployment_details,
)


class TestIBHelpers(unittest.TestCase):
    @patch("requests.patch")
    def test_upload_chunks(self, mock_patch):
        mock_patch.return_value.status_code = 204
        response = upload_chunks("https://example.com", "path", "token", b"data")
        self.assertEqual(response.status_code, 204)

    @patch("requests.put")
    def test_upload_file(self, mock_put):
        mock_put.return_value.status_code = 204
        response = upload_file("https://example.com", "token", "path", b"data")
        self.assertEqual(response.status_code, 204)

    @patch("requests.get")
    def test_read_file_through_api(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.content = b"file content"
        response = read_file_through_api("https://example.com", "token", "path")
        self.assertEqual(response.status_code, 200)

    @patch("requests.post")
    def test_publish_to_marketplace(self, mock_post):
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"status": "success"}
        response = publish_to_marketplace("https://example.com", "token", "path")
        self.assertEqual(response.status_code, 200)

    @patch("requests.get")
    @patch("requests.post")
    def test_make_api_request(self, mock_post, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"data": "success"}
        response = make_api_request("https://example.com", "token", method="get")
        self.assertEqual(response["data"], "success")

        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {"data": "posted"}
        response = make_api_request(
            "https://example.com", "token", method="post", payload={"key": "value"}
        )
        self.assertEqual(response["data"], "posted")

    @patch("requests.get")
    def test_check_job_status(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.content = json.dumps({"status": "completed"}).encode()
        response = check_job_status("https://example.com", "job_id", "flow", "token")
        self.assertEqual(response.status_code, 200)

    @patch("requests.get")
    @patch("time.sleep", return_value=None)
    def test_check_job_status_build_success(self, mock_sleep, mock_get):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "state": "DONE",
            "results": [{"deployed_solution_id": "12345"}],
        }
        mock_get.return_value = mock_response

        result = check_job_status_build("http://test-url", "api-token", "job-id")

        self.assertEqual(result, "12345")
        mock_get.assert_called_with(
            "http://test-url/api/v1/jobs/status?job_id=job-id&type=async",
            headers={"Authorization": "Bearer api-token"},
            verify=True,
        )

    @patch("requests.post")
    def test_unzip_files_success(self, mock_post):
        mock_response = Mock()
        mock_response.status_code = 202
        mock_post.return_value = mock_response

        resp = unzip_files(
            "http://test-url", "api-token", "test.zip", "test-destination"
        )

        self.assertEqual(resp, mock_response)
        mock_post.assert_called_with(
            "http://test-url/api/v2/files/extract",
            headers={"Authorization": "Bearer api-token"},
            data=json.dumps({"src_path": "test.zip", "dst_path": "test-destination"}),
            verify=False,
        )

    @patch("requests.post")
    def test_compile_solution_success(self, mock_post):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "SUCCESS"}
        mock_response.content = json.dumps({"status": "SUCCESS"}).encode()
        mock_post.return_value = mock_response

        response = compile_solution(
            "http://test-url", "api-token", "solution-path", "relative-path.ibflow"
        )

        self.assertEqual(response, mock_response)
        mock_post.assert_called_once()

    @patch("requests.post")
    def test_copy_file_within_ib_api(self, mock_post):
        # Setup mock response
        mock_response = MagicMock()
        mock_response.status_code = 202
        mock_post.return_value = mock_response

        # Call the function
        response = copy_file_within_ib(
            "http://test.com",
            "fake_token",
            "/source",
            "/destination",
            use_clients=False,
        )

        # Assertions
        self.assertEqual(response.status_code, 202)
        mock_post.assert_called_once_with(
            "http://test.com/api/v2/files/copy",
            headers={"Authorization": "Bearer fake_token"},
            data=json.dumps({"src_path": "/source", "dst_path": "/destination"}),
            verify=False,
        )

    @patch("requests.post")
    @patch("requests.head")
    def test_create_folder_if_it_does_not_exists(self, mock_head, mock_post):
        # Setup mock responses
        mock_head_response = MagicMock()
        mock_head_response.status_code = 404
        mock_head.return_value = mock_head_response

        mock_post_response = MagicMock()
        mock_post_response.status_code = 201
        mock_post.return_value = mock_post_response

        # Call the function
        response = create_folder_if_it_does_not_exists(
            "http://test.com", "fake_token", "/path/to/folder"
        )

        # Assertions
        self.assertEqual(response.status_code, 201)
        mock_head.assert_called_once_with(
            "/path/to/folder",
            headers={"Authorization": "Bearer fake_token"},
            verify=False,
        )
        mock_post.assert_called_once_with(
            "/path/to",
            headers={"Authorization": "Bearer fake_token"},
            data=json.dumps({"name": "folder", "node_type": "folder"}),
            verify=False,
        )

    @patch("requests.get")
    def test_list_directory(self, mock_get):
        # Setup mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = json.dumps(
            {
                "nodes": [
                    {"full_path": "/path/to/file1"},
                    {"full_path": "/path/to/file2"},
                ],
                "has_more": False,
                "next_page_token": None,
            }
        )
        mock_get.return_value = mock_response

        # Call the function
        paths = list_directory("http://test.com", "/folder", "fake_token")

        # Assertions
        self.assertEqual(paths, ["/path/to/file1", "/path/to/file2"])
        mock_get.assert_called_once_with(
            "/folder",
            headers={"Authorization": "Bearer fake_token"},
            params={"expect-node-type": "folder", "start-token": None},
        )

    @patch("requests.head")
    def test_get_file_metadata(self, mock_head):
        # Setup mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b""
        mock_head.return_value = mock_response

        # Call the function
        response = get_file_metadata("http://test.com", "fake_token", "/path/to/file")

        # Assertions
        self.assertEqual(response.status_code, 200)
        mock_head.assert_called_once_with(
            "/path/to/file",
            headers={
                "Authorization": "Bearer fake_token",
                "IB-Retry-Config": json.dumps({"retries": 2, "backoff-seconds": 1}),
            },
        )

    @patch("requests.delete")
    def test_delete_folder_or_file_from_ib(self, mock_delete):
        # Setup mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_delete.return_value = mock_response

        # Call the function
        delete_folder_or_file_from_ib(
            "/path/to/delete", "http://test.com", "fake_token", use_clients=False
        )

        # Assertions
        mock_delete.assert_called_once_with(
            "/path/to/delete",
            headers={"Authorization": "Bearer fake_token"},
            verify=False,
        )

    @patch("requests.post")
    def test_generate_flow(self, mock_post):
        # Setup mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "success"}
        mock_post.return_value = mock_response

        # Patch reading image
        with patch(
            "builtins.open",
            new_callable=unittest.mock.mock_open,
            read_data=b"fake_image_data",
        ):
            response = generate_flow(
                "http://test.com", "fake_token", "fake_project_id", "fake_icon_path"
            )

        # Assertions
        self.assertEqual(response["status"], "success")
        mock_post.assert_called_once()

    @patch("requests.get")
    def test_read_file_content_from_ib_api(self, mock_get):
        # Setup mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"file_content"
        mock_get.return_value = mock_response

        # Call the function
        content = read_file_content_from_ib(
            "http://test.com", "fake_token", "/path/to/file", use_clients=False
        )

        # Assertions
        self.assertEqual(content, b"file_content")
        mock_get.assert_called_once_with(
            "/path/to/file",
            headers={"Authorization": "Bearer fake_token"},
            params={"expect-node-type": "file"},
            verify=False,
        )

    @patch("requests.get")
    def test_read_file_content_from_ib_clients(self, mock_get):
        # Setup mock client response
        clients_mock = MagicMock()
        clients_mock.ibfile.is_file.return_value = True
        clients_mock.ibfile.read_file.return_value = (
            b"file_content",
            None,
        )  # Return tuple of content and error

        # Mock the CLIENTS column to return the proper tuple
        mock_clients = MagicMock()
        clients_mock.get_by_col_name.return_value = (mock_clients, None)
        mock_clients.ibfile.is_file.return_value = True
        mock_clients.ibfile.read_file.return_value = (
            b"file_content",
            None,
        )  # Return tuple of content and error

        # Call the function
        content = read_file_content_from_ib(
            "http://test.com",
            "fake_token",
            "/path/to/file",
            use_clients=True,
            **{"_FN_CONTEXT_KEY": clients_mock},
        )

        # Assertions
        self.assertEqual(content, b"file_content")
        clients_mock.get_by_col_name.assert_called_once_with("CLIENTS")
        mock_clients.ibfile.read_file.assert_called_once_with("/path/to/file")

    @patch("requests.get")
    def test_wait_until_job_finishes_success(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.content = json.dumps(
            {"status": "OK", "state": "DONE"}
        ).encode()

        result = wait_until_job_finishes(
            "https://example.com", "job_id", "flow", "token"
        )
        self.assertTrue(result)

    @patch("requests.get")
    def test_wait_until_job_finishes_failure(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.content = json.dumps({"status": "ERROR"}).encode()

        with self.assertRaises(Exception) as context:
            wait_until_job_finishes("https://example.com", "job_id", "flow", "token")

        self.assertIn("Error checking job status", str(context.exception))

    @patch("requests.delete")
    def test_delete_app_success(self, mock_delete):
        mock_delete.return_value.status_code = 204

        response = delete_app("https://example.com", "token", "app_id", "org")
        self.assertEqual(response.status_code, 204)

    @patch("requests.delete")
    def test_delete_app_failure(self, mock_delete):
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError()
        mock_delete.return_value = mock_response

        with self.assertRaises(requests.exceptions.HTTPError):
            delete_app("https://example.com", "token", "app_id", "org")

    @patch("requests.get")
    def test_get_app_details(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"app": "details"}

        response = get_app_details("https://example.com", "token", "context", "app_id")
        self.assertEqual(response["app"], "details")

    @patch("requests.get")
    def test_get_deployment_details(self, mock_get):
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {"deployment": "details"}

        response = get_deployment_details(
            "https://example.com", "token", "context", "deployment_id"
        )
        self.assertEqual(response["deployment"], "details")


if __name__ == "__main__":
    unittest.main()
