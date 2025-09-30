import unittest
from unittest.mock import patch, MagicMock
import json
import pathlib
from ib_cicd.promote_sb_solution import (
    get_latest_flow_version,
    get_sb_flow_path,
)


class TestPromoteSBSolution(unittest.TestCase):
    @patch("ib_cicd.promote_sb_solution.list_directory")
    def test_get_latest_flow_version(self, mock_list_directory):
        # Mock directory listing with versioned flows
        mock_list_directory.return_value = [
            "flows/1.0.0.ibflow",
            "flows/1.2.0.ibflow",
            "flows/2.0.1.ibflow",
            "flows/0.9.5.ibflow",
        ]

        latest_version = get_latest_flow_version("/flows", "mock_host", "mock_token")
        self.assertEqual(latest_version, "2.0.1")

        # Test with no versions
        mock_list_directory.return_value = []
        latest_version = get_latest_flow_version("/flows", "mock_host", "mock_token")
        self.assertEqual(latest_version, "0.0.0")

        # Test with an exception
        mock_list_directory.side_effect = Exception("API error")
        with self.assertRaises(Exception):
            get_latest_flow_version("/flows", "mock_host", "mock_token")

    @patch("ib_cicd.promote_sb_solution.list_directory")
    @patch("ib_cicd.promote_sb_solution.read_file_through_api")
    def test_get_sb_flow_path(self, mock_read_file, mock_list_directory):
        # Mocked metadata JSON response
        mock_metadata = {"name": "TestFlow", "versions_tree": {"version_id": "v1.0.0"}}
        mock_read_file.return_value.content = json.dumps(mock_metadata)

        # Mock directory listing
        mock_list_directory.return_value = ["/flows/TestFlow"]

        flow_path = get_sb_flow_path(
            "SolutionBuilder", "TestFlow", "/ib_root", "mock_host", "mock_token"
        )
        self.assertEqual(flow_path, "/flows/TestFlow/versions/v1.0.0")

        # Test when flow is not found
        mock_list_directory.return_value = []
        with self.assertRaises(FileNotFoundError):
            get_sb_flow_path(
                "SolutionBuilder",
                "NonExistentFlow",
                "/ib_root",
                "mock_host",
                "mock_token",
            )

        # Test with API error
        mock_list_directory.side_effect = Exception("API failure")
        with self.assertRaises(Exception):
            get_sb_flow_path(
                "SolutionBuilder", "TestFlow", "/ib_root", "mock_host", "mock_token"
            )


if __name__ == "__main__":
    unittest.main()
