import unittest
from unittest.mock import patch, Mock

from ib_cicd.rebuild_utils import (
    create_build_project,
    clean_function_data,
    get_settings,
    post_settings,
    modify_settings,
    get_udfs,
    post_udf,
    sanitize_udf_payload,
    generate_id,
    get_schema,
    post_schema,
    get_item_ids,
    modify_udf_lines,
    modify_schema,
    get_validations,
    post_validations,
    delete_validations,
    update_fields_with_mapping,
    map_field_ids,
    modify_validations,
)


class TestRebuildUtils(unittest.TestCase):
    @patch("requests.post")
    def test_create_build_project(self, mock_post):
        mock_response = Mock()
        mock_response.json.return_value = {"id": "123"}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        result = create_build_project(
            "test_project", "token", "http://example.com", "org", "workspace"
        )
        self.assertEqual(result, {"id": "123"})
        mock_post.assert_called_once()

    def test_clean_function_data(self):
        function_data = {
            "id": "1",
            "name": "test",
            "docstring": "test",
            "last_updated_at": "2023-01-01",
            "lambda_id": "123",
            "lambda_udf_id": "456",
            "lambda_end_of_life": "2024-01-01",
        }
        clean_function_data(function_data)
        self.assertNotIn("docstring", function_data)
        self.assertNotIn("last_updated_at", function_data)
        self.assertNotIn("lambda_id", function_data)
        self.assertNotIn("lambda_udf_id", function_data)
        self.assertNotIn("lambda_end_of_life", function_data)
        self.assertEqual(function_data["return_type"], "string")

    @patch("requests.get")
    def test_get_settings(self, mock_get):
        mock_response = Mock()
        mock_response.json.return_value = {"settings": "test"}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = get_settings("project_id", "token", "http://example.com")
        self.assertEqual(result, {"settings": "test"})
        mock_get.assert_called_once()

    @patch("requests.patch")
    def test_post_settings(self, mock_patch):
        mock_response = Mock()
        mock_response.text = "success"
        mock_response.raise_for_status.return_value = None
        mock_patch.return_value = mock_response

        result = post_settings(
            "project_id", "token", "http://example.com", {"setting": "value"}
        )
        self.assertEqual(result, "success")
        mock_patch.assert_called_once()

    def test_modify_settings(self):
        response = {
            "projects": [
                {"id": "project_id", "name": "test", "desc": "test", "llm": ""}
            ]
        }
        result = modify_settings("project_id", response)
        self.assertIn('"name": "test"', result)

    @patch("requests.get")
    def test_get_udfs(self, mock_get):
        mock_response = Mock()
        mock_response.json.return_value = {"udfs": "test"}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = get_udfs("project_id", "token", "http://example.com")
        self.assertEqual(result, {"udfs": "test"})
        mock_get.assert_called_once()

    @patch("requests.post")
    def test_post_udf(self, mock_post):
        mock_response = Mock()
        mock_response.json.return_value = {"udf_id": "123"}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        result = post_udf("project_id", "token", "http://example.com", {"udf": "test"})
        self.assertEqual(result, {"udf_id": "123"})
        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        self.assertEqual(kwargs["headers"].get("Authorization"), "Bearer token")
        self.assertIn("IB-Certificate", kwargs["headers"])

    def test_sanitize_udf_payload(self):
        payload = {
            "1": {
                "docstring": "test",
                "last_updated_at": "2023-01-01",
                "lambda_id": "123",
                "lambda_udf_id": "456",
                "lambda_end_of_life": "2024-01-01",
            }
        }
        result = sanitize_udf_payload(payload)
        self.assertNotIn("docstring", result["1"])
        self.assertEqual(result["1"]["return_type"], "string")

    def test_generate_id(self):
        id = generate_id()
        self.assertEqual(len(id), 21)

    @patch("requests.get")
    def test_get_schema(self, mock_get):
        mock_response = Mock()
        mock_response.json.return_value = {"schema": "test"}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = get_schema("project_id", "token", "http://example.com")
        self.assertEqual(result, {"schema": "test"})
        mock_get.assert_called_once()

    @patch("requests.post")
    def test_post_schema(self, mock_post):
        mock_response = Mock()
        mock_response.json.return_value = {"schema_id": "123"}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        result = post_schema(
            "project_id", "token", "http://example.com", {"schema": "test"}
        )
        self.assertEqual(result, {"schema_id": "123"})
        mock_post.assert_called_once()

    def test_get_item_ids(self):
        schema = {
            "1": {"name": "test1"},
            "2": {"name": "test2"},
            "last_edited_at": "2023-01-01",
        }
        result = get_item_ids(schema)
        self.assertEqual(result, {"test1": "1", "test2": "2"})

    @patch("ib_cicd.rebuild_utils.post_udf")
    def test_modify_udf_lines(self, mock_post_udf):
        mock_post_udf.return_value = {"udf_id": "123"}
        field_schema = {"lines": [{"line_type": "UDF", "function_id": "1"}]}
        udfs = {"1": {"udf": "test"}}
        modify_udf_lines(
            field_schema, "project_id", "token", "http://example.com", udfs
        )
        self.assertEqual(field_schema["lines"][0]["function_id"], "123")

    def test_modify_schema(self):
        target_schema = {
            "1": {
                "name": "test1",
                "description": "A test class",
                "fields": {"1": {"name": "field1", "lines": []}},
            }
        }
        source_schema = {
            "2": {
                "name": "test1",
                "description": "A test class",
                "fields": {"2": {"name": "field1", "lines": []}},
            }
        }
        udfs = {}
        result = modify_schema(
            target_schema,
            source_schema,
            "project_id",
            "token",
            "http://example.com",
            udfs,
        )
        self.assertIn("classes", result)

    @patch("requests.get")
    def test_get_validations(self, mock_get):
        mock_response = Mock()
        mock_response.json.return_value = {"validations": "test"}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = get_validations("project_id", "token", "http://example.com")
        self.assertEqual(result, {"validations": "test"})
        mock_get.assert_called_once()
        _, kwargs = mock_get.call_args
        self.assertEqual(kwargs["headers"].get("Authorization"), "Bearer token")
        self.assertIn("IB-Certificate", kwargs["headers"])

    @patch("requests.post")
    def test_post_validations(self, mock_post):
        mock_response = Mock()
        mock_response.json.return_value = {"validation_id": "123"}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        result = post_validations(
            "project_id", "token", "http://example.com", {"validation": "test"}
        )
        self.assertEqual(result, {"validation_id": "123"})
        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        self.assertEqual(kwargs["headers"].get("Authorization"), "Bearer token")
        self.assertIn("IB-Certificate", kwargs["headers"])

    @patch("requests.delete")
    def test_delete_validations(self, mock_delete):
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_delete.return_value = mock_response

        result = delete_validations("project_id", "token", "http://example.com", "1")
        self.assertEqual(result, mock_response)
        mock_delete.assert_called_once()
        _, kwargs = mock_delete.call_args
        self.assertEqual(kwargs["headers"].get("Authorization"), "Bearer token")
        self.assertIn("IB-Certificate", kwargs["headers"])

    def test_update_fields_with_mapping(self):
        fields = [1, 2]
        mappings = {"1": 10, "2": 20}
        result = update_fields_with_mapping(fields, mappings)
        self.assertEqual(result, [10, 20])

    def test_map_field_ids(self):
        old_schema = {"1": {"name": "test1", "fields": {"1": {"name": "field1"}}}}
        new_schema = {"2": {"name": "test1", "fields": {"2": {"name": "field1"}}}}
        result = map_field_ids(old_schema, new_schema)
        self.assertEqual(result, {"1": "2"})

    @patch("ib_cicd.rebuild_utils.post_udf")
    @patch("ib_cicd.rebuild_utils.delete_validations")
    def test_modify_validations(self, mock_delete_validations, mock_post_udf):
        mock_post_udf.return_value = {"udf_id": "123"}
        mock_delete_validations.return_value = Mock()

        target_validations = {"rules": [{"name": "test", "id": "1"}]}
        source_validations = {
            "rules": [{"name": "test", "type": "UDF", "params": {"udf_id": "1"}}]
        }
        udfs = {"1": {"udf": "test"}}
        mappings = {"1": "10"}
        result = modify_validations(
            target_validations,
            source_validations,
            "project_id",
            "token",
            "http://example.com",
            udfs,
            mappings,
        )
        self.assertIsInstance(result, list)


if __name__ == "__main__":
    unittest.main()
