import json
import requests
import time
from uuid import uuid4
import copy


def create_build_project(project_name, token, target_url, org, workspace, proxies=None):
    """Creates a build project in the target environment"""
    url = f"{target_url}/api/v2/aihub/build/projects"
    headers = {"Authorization": f"Bearer {token}", "Ib-Context": org}
    current_unix_timestamp = int(time.time())
    data = {
        "name": project_name,
        "desc": project_name,
        "llm": "",
        "reader_profile": {
            "foundationVersion": "",
            "schema": "1",
            "createdOn": current_unix_timestamp,
            "createdBy": "",
            "lastModifiedOn": current_unix_timestamp,
            "lastModifiedBy": "",
            "inputPath": None,
            "outputPath": None,
            "defaultProfile": "",
        },
        "extraction_mode": None,
        "org": org,
        "workspace": workspace,
        "creation_base": "NONE",
    }

    response = requests.post(url=url, headers=headers, json=data, proxies=proxies)
    response.raise_for_status()
    return response.json()


#### Functions for Settings ####


def clean_function_data(function_data):
    """Remove unnecessary fields and set return type."""
    fields_to_remove = ["id", "project_root", "data_root", "workspace", "name"]

    for field in fields_to_remove:
        function_data.pop(field, None)


def get_settings(project_id, token, host_url, proxies=None):
    """
    Return the schema response
        Args:
            project_id: the build project id
            token: auth token
            host_url: the environment project is in
        Return:
            ocr settings response
    """

    get_ocr_url = (
        f"{host_url}/api/v2/aihub/build/projects?proj_id={project_id}&query_option=uuid"
    )
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(url=get_ocr_url, headers=headers, proxies=proxies)
    response.raise_for_status()  # This will raise an error
    return response.json()


def post_settings(project_id, token, host_url, data, proxies=None):
    """
    Return the schema response
        Args:
            project_id: the build project id
            token: auth token
            host_url: the environment project is in
            data: target ocr settings to be added
        Return:
            status response
    """
    get_ocr_url = f"{host_url}/api/v2/aihub/build/projects?project_id={project_id}"
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.patch(
        url=get_ocr_url, headers=headers, data=data, proxies=proxies
    )
    response.raise_for_status()  # This will raise an error
    return response.text


def modify_settings(project_id, response):
    payload = {}
    for item in response["projects"]:
        if item["id"] == project_id:
            payload = item
            clean_function_data(payload)
            break
    return json.dumps(payload, indent=4)


#### Function for UDFs ####


def get_udfs(project_id, token, host_url, proxies=None):
    """
    Return the udfs response
        Args:
            project_id: the build project id
            token: auth token
            host_url: the environment project is in
        Return:
            schema response
    """

    get_udfs_url = f"{host_url}/api/v2/aihub/build/projects/{project_id}/udfs"
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(url=get_udfs_url, headers=headers, proxies=proxies)
    response.raise_for_status()  # This will raise an error
    return response.json()


def post_udf(project_id, token, target_url, data, proxies=None):
    """
    Return the json response
        Args:
            project_id: the build project id
            token: auth token
            host_url: the environment project is in
            data: target udfs to be added
        Return:
            json response
    """
    post_udfs_url = f"{target_url}/api/v2/aihub/build/projects/{project_id}/udfs"
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.post(
        url=post_udfs_url, headers=headers, json=data, proxies=proxies
    )
    response.raise_for_status()
    return response.json()


def clean_function_data(function_data):
    """Remove unnecessary fields and set return type."""
    fields_to_remove = [
        "docstring",
        "last_updated_at",
        "lambda_id",
        "lambda_udf_id",
        "lambda_end_of_life",
    ]

    for field in fields_to_remove:
        function_data.pop(
            field, None
        )  # Use pop to avoid KeyError if the field does not exist

    function_data["return_type"] = "string"


def sanitize_udf_payload(result):
    """Create a sanitized payload for UDFS."""
    payload = copy.deepcopy(result)

    for function_id in payload:
        clean_function_data(payload[function_id])

    return payload


#### Functions for Schema ####


def generate_id():
    uuid = str(uuid4()).replace("-", "")
    return uuid[:21]


def get_schema(project_id, token, host_url, proxies=None):
    """
    Return the schema response
        Args:
            project_id: the build project id
            token: auth token
            host_url: the environment project is in
        Return:
            schema response
    """

    get_schema_url = f"{host_url}/api/v2/aihub/build/projects/{project_id}/schema"
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(url=get_schema_url, headers=headers, proxies=proxies)
    response.raise_for_status()  # This will raise an error
    return response.json()


def post_schema(project_id, token, target_url, data, proxies=None):
    """
    Return the json response
        Args:
            project_id: the build project id
            token: auth token
            host_url: the environment project is in
            data: target schema to be added
        Return:
            json response
    """
    post_schema_url = f"{target_url}/api/v2/aihub/build/projects/{project_id}/schema"
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.post(
        url=post_schema_url, headers=headers, json=data, proxies=proxies
    )
    response.raise_for_status()
    return response.json()


def get_item_ids(schema):
    """Returns a dictionary in the format: {'field/class name': 'ID'}"""
    items = {}
    for key, value in schema.items():
        if key not in ["last_edited_at", "last_edited_class_at"]:
            name = value["name"]
            items[name] = key
    return items


def run_prompt_udf(project_id, token, target_url, validation_id, proxies=None):
    """Generates code for a prompt UDF"""
    url = f"{target_url}/api/v2/aihub/build/projects/{project_id}/validations/{validation_id}/examples"
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.put(url=url, headers=headers, proxies=proxies)
    response.raise_for_status()
    time.sleep(10)

    url = f"{target_url}/api/v2/aihub/build/projects/{project_id}/validations/{validation_id}/code-generation"
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.put(url=url, headers=headers, proxies=proxies)
    response.raise_for_status()
    time.sleep(10)
    return response.json()


def modify_udf_lines(field_schema, project_id, token, target_url, udfs, proxies=None):
    for line in field_schema["lines"]:
        if line["line_type"] == "UDF":
            function_id = line["function_id"]
            result = post_udf(
                project_id, token, target_url, udfs[str(function_id)], proxies=proxies
            )
            line["function_id"] = result["udf_id"]


def modify_schema(
    target_schema, source_schema, project_id, token, target_url, udfs, proxies=None
):
    """
    Function to create the payload
        Args:
            target_schema: Outdated
            source_schema: Latest
        Returns:
            Payload Dictionary
    """

    # Get the names and IDs of the classes in source and target schemas
    source_classes = get_item_ids(source_schema)
    target_classes = get_item_ids(target_schema)

    # Identify if the class already exists or requires to be added
    classes, new_classes = {}, []

    for class_name, source_class_id in source_classes.items():
        # Get the names and IDs of the fields in source env
        source_class_schema = source_schema[source_class_id]
        source_fields = get_item_ids(source_class_schema["fields"])
        source_fields_schema = source_class_schema["fields"]

        class_schema = {
            "name": source_class_schema["name"],
            "description": source_class_schema["description"],
            "fields": {},
            "new_fields": [],
        }

        if class_name in target_classes:  # or class_name == 'Other':
            # Get the names and ids of the existing fields in target env
            # 'DEFAULT_CLASS_NAME' if class_name == 'Other' else
            target_class_id = target_classes[class_name]
            target_class_schema = target_schema[target_class_id]
            target_fields = get_item_ids(target_class_schema["fields"])

            # Identify if the field already exists or requires to be added
            fields, new_fields = {}, []

            for field_name, source_field_id in source_fields.items():
                # Get the source field schema
                source_field_schema = source_fields_schema[source_field_id]

                field_schema = source_field_schema.copy()

                if field_name in target_fields:
                    # Get the target field id
                    target_field_id = target_fields[field_name]
                    # Add the new schema to target
                    modify_udf_lines(
                        field_schema,
                        project_id,
                        token,
                        target_url,
                        udfs,
                        proxies=proxies,
                    )
                    fields[target_field_id] = field_schema
                else:
                    modify_udf_lines(
                        field_schema,
                        project_id,
                        token,
                        target_url,
                        udfs,
                        proxies=proxies,
                    )
                    field_schema["uuid"] = generate_id()
                    new_fields.append(field_schema)

            # Set the schema from source class and updated fields
            class_schema["fields"] = fields
            class_schema["new_fields"] = new_fields
            classes[target_class_id] = class_schema
        else:
            # Add all the fields under new_fields
            new_fields = []

            for field_name in source_fields:
                # Get the source field schema
                source_field_id = source_fields[field_name]
                source_field_schema = source_fields_schema[source_field_id]

                field_schema = source_field_schema.copy()
                modify_udf_lines(
                    field_schema, project_id, token, target_url, udfs, proxies=proxies
                )
                field_schema["uuid"] = generate_id()
                new_fields.append(field_schema)

            class_schema["new_fields"] = new_fields
            new_classes.append(class_schema)

    return {"classes": classes, "new_classes": new_classes}


#### Functions for validations ####


def get_validations(project_id, token, host_url, proxies=None):
    """
    Return the validations response
        Args:
            project_id: the build project id
            token: auth token
            host_url: the environment project is in
        Return:
            schema response
    """

    get_validations_url = (
        f"{host_url}/api/v2/aihub/build/projects/{project_id}/validations"
    )
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(url=get_validations_url, headers=headers, proxies=proxies)
    response.raise_for_status()  # This will raise an error
    return response.json()


def post_validations(project_id, token, target_url, data, proxies=None):
    """
    Return the json response
        Args:
            project_id: the build project id
            token: auth token
            host_url: the environment project is in
            data: target validations to be added
        Return:
            json response
    """
    post_udfs_url = f"{target_url}/api/v2/aihub/build/projects/{project_id}/validations"
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.post(
        url=post_udfs_url, headers=headers, json=data, proxies=proxies
    )
    response.raise_for_status()
    return response.json()


def delete_validations(project_id, token, target_url, id, proxies=None):
    """
    Delete a particular validation
    """
    delete_url = (
        f"{target_url}/api/v2/aihub/build/projects/{project_id}/validations?id={id}"
    )
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.delete(url=delete_url, headers=headers, proxies=proxies)
    response.raise_for_status()
    return response


def update_fields_with_mapping(fields, mappings):
    """
    This function updates a list of field IDs based on a provided mapping.
    """
    result = []
    for f in fields:
        result.append(int(mappings[str(f)]))
    return result


def get_item_ids(schema):
    """Returns a dictionary in the format: {'field/class name': 'ID'}"""
    items = {}
    for key, value in schema.items():
        if key not in ["last_edited_at", "last_edited_class_at"]:
            name = value["name"]
            items[name] = key
    return items


def map_field_ids(old_schema, new_schema):
    """
    Maps old schema field IDs to new schema field IDs based on matching names.
        Args:
            old_schema: Old schema dictionary
            new_schema: New schema dictionary
        Returns:
            field_id_mapping: Dictionary mapping old field IDs to new field IDs
    """

    field_id_mapping = {}
    old_classes = get_item_ids(old_schema)
    new_classes = get_item_ids(new_schema)

    for old_class_name, old_class_id in old_classes.items():
        if old_class_name in new_classes:
            new_class_id = new_classes[old_class_name]
            field_id_mapping[old_class_id] = new_class_id
            old_fields = get_item_ids(old_schema[old_class_id]["fields"])
            new_fields = get_item_ids(new_schema[new_class_id]["fields"])

            # Map each old field ID to the new field ID if field names match
            for old_field_name, old_field_id in old_fields.items():
                if old_field_name in new_fields:
                    new_field_id = new_fields[old_field_name]
                    field_id_mapping[old_field_id] = new_field_id
    return field_id_mapping


def modify_validations(
    target_validations,
    source_validations,
    project_id,
    token,
    target_url,
    udfs,
    mappings,
    proxies=None,
):
    """
    Function to create the payload for validations
        Args:
            target_schema: That needs to be updated
            source_schema: the source we are copying from
        Returns:
            Payload Dictionary
    """

    # to find if the validation is already present
    names = {}
    for rule in target_validations["rules"]:
        names[rule.get("name")] = rule.get("id")

    # Convert the data to payloads
    payloads = []
    for rule in source_validations["rules"]:
        if rule.get("name") in names.keys():
            response = delete_validations(
                project_id, token, target_url, names[rule.get("name")], proxies=proxies
            )

        payload = {
            "projectId": project_id,
            "name": rule.get("name"),
            "type": rule.get("type"),
            "affected_fields": update_fields_with_mapping(
                rule.get("affected_fields", []), mappings
            ),
            "alert_level": rule.get("alert_level"),
            "scope": rule.get("scope"),
            "description": rule.get("description", ""),
            "input_fields": update_fields_with_mapping(
                rule.get("input_fields", []), mappings
            ),
            "params": rule.get("params", {}),
        }

        if rule.get("type") == "CLASS_CONFIDENCE":
            payload["params"]["affected_classes"] = update_fields_with_mapping(
                payload["params"]["affected_classes"], mappings
            )

        if rule.get("type") == "UDF" or rule.get("type") == "PROMPT_UDF":
            id = rule["params"]["udf_id"]
            response = post_udf(
                project_id, token, target_url, udfs[str(id)], proxies=proxies
            )
            new_id = response["udf_id"]

            headers = {"Authorization": f"Bearer {token}"}
            examples_url = f"{target_url}/api/v2/aihub/build/projects/{project_id}/validations/{new_id}/examples"
            resp = requests.put(examples_url, headers=headers, proxies=proxies)
            print(f"Run Examples {new_id}: {resp.text}")

            payload["params"]["udf_id"] = int(new_id)

        payloads.append(payload)

    return payloads
