import argparse
import json
import os
import pathlib
import re
import time

from ib_cicd.ib_helpers import (
    wait_until_job_finishes,
    create_deployment,
    generate_flow,
    get_app_details,
    get_deployment_details,
    get_published_app_id,
    read_file_through_api,
    delete_app,
    publish_build_app,
    delete_build_project,
    list_directory,
    unzip_files,
    delete_folder_or_file_from_ib,
    download_regression_suite,
    trigger_regression_run,
    upload_file,
    read_image,
    create_folder_if_it_does_not_exists,
    add_the_state,
)


from ib_cicd.rebuild_utils import (
    create_build_project,
    get_schema,
    get_settings,
    get_udfs,
    get_validations,
    map_field_ids,
    modify_schema,
    modify_settings,
    modify_validations,
    post_schema,
    post_settings,
    post_validations,
    sanitize_udf_payload,
    run_prompt_udf,
)


def download_file(ib_host, api_token, solution_path, proxies=None):
    """
    Download a JSON file from the Instabase API.
    """
    response = read_file_through_api(ib_host, api_token, solution_path, proxies=proxies)
    if not response or response.status_code != 200:
        raise Exception(
            f"We couldn't download your file from {solution_path}. This could be because the file doesn't exist or you don't have permission to access it. Please check the path and try again."
        )

    solution_name = pathlib.Path(solution_path).name
    try:
        json_content = json.loads(response.content.decode("utf-8"))
        with open(solution_name, "w") as fd:
            json.dump(json_content, fd, indent=4, sort_keys=True)
        return response.content
    except json.JSONDecodeError as e:
        raise Exception(
            f"The file we downloaded isn't in the correct format. It should be a valid JSON file. Please check the file and try again. {e}"
        )


def save_to_file(data, file_name):
    """Save data to a JSON file."""
    with open(file_name, "w") as f:
        json.dump(data, f, indent=4, sort_keys=True)


def read_binary(file_name="codelabs.ibflowbin"):
    """Read binary data from a file."""
    with open(file_name, "rb") as f:
        data = f.read()
    return data


def load_from_file(file_name):
    """Load data from a JSON file."""
    if os.path.exists(file_name):
        with open(file_name, "r") as f:
            return json.load(f)
    else:
        raise FileNotFoundError(
            f"We couldn't find the file: {file_name}. Please make sure the file exists in the correct location and try again."
        )


def load_config(file_path="config.json"):
    """Load configuration from a JSON file."""
    try:
        with open(file_path, "r") as config_file:
            config = json.load(config_file)
        print("Configuration file loaded successfully")
        return config
    except FileNotFoundError:
        raise FileNotFoundError(
            f"We couldn't find your configuration file '{file_path}'. Make sure it exists in your current directory."
        )
    except json.JSONDecodeError:
        raise Exception(
            f"Error in your configuration file '{file_path}'. Please check that it's valid JSON."
        )
    except Exception as e:
        raise Exception(
            f"Something went wrong while reading your configuration file: {e}. "
            f"Please check your config and environment, or contact support."
        )


def fetch_details(config, proxies=None):
    """Fetch phase information (settings, schema, validations, etc.)."""
    source_host_url = os.environ.get("SOURCE_HOST_URL")
    source_token = os.environ.get("SOURCE_TOKEN")
    source_project_id = config["source"]["project_id"]

    try:
        projects = get_settings(
            source_project_id, source_token, source_host_url, proxies=proxies
        )
        save_to_file(projects, "fetched_settings.json")

        udfs = get_udfs(
            source_project_id, source_token, source_host_url, proxies=proxies
        )
        save_to_file(udfs, "fetched_udfs.json")

        schema = get_schema(
            source_project_id, source_token, source_host_url, proxies=proxies
        )
        save_to_file(schema, "fetched_schema.json")

        validations = get_validations(
            source_project_id, source_token, source_host_url, proxies=proxies
        )
        save_to_file(validations, "fetched_validations.json")

    except Exception as e:
        raise Exception(
            f"We couldn't fetch all the necessary information from your project. This might be due to connection issues or missing permissions. Error details: {e}"
        )


def rebuild_project(config, proxies=None):
    """Rebuild the project in the target environment."""
    target_token = os.environ.get("TARGET_TOKEN")
    target_host_url = os.environ.get("TARGET_HOST_URL")
    target_org = config["target"]["org"]
    target_workspace = config["target"]["workspace"]
    source_project_id = config["source"]["project_id"]

    try:
        # Load fetched data
        projects = load_from_file("fetched_settings.json")
        udfs = load_from_file("fetched_udfs.json")
        schema = load_from_file("fetched_schema.json")
        validations = load_from_file("fetched_validations.json")

        # Create build project
        target_project_id = config["target"].get("project_id")
        if not target_project_id:
            project_name = next(
                (
                    item["name"]
                    for item in projects["projects"]
                    if item["id"] == source_project_id
                ),
                None,
            )
            if not project_name:
                raise ValueError(
                    "We couldn't find your source project in the settings. Please check that your project ID is correct."
                )

            response = create_build_project(
                project_name,
                target_token,
                target_host_url,
                target_org,
                target_workspace,
                proxies=proxies,
            )
            target_project_id = response["project_id"]

            config["target"]["project_id"] = target_project_id
            save_to_file(config, "config.json")

        # Modify and post settings, schema, and validations
        modified_settings = modify_settings(source_project_id, projects)
        post_settings(
            target_project_id,
            target_token,
            target_host_url,
            modified_settings,
            proxies=proxies,
        )

        sanitized_udfs = sanitize_udf_payload(udfs)
        target_schema = get_schema(
            target_project_id, target_token, target_host_url, proxies=proxies
        )
        modified_schema = modify_schema(
            target_schema,
            schema,
            target_project_id,
            target_token,
            target_host_url,
            sanitized_udfs,
        )
        result = post_schema(
            target_project_id,
            target_token,
            target_host_url,
            modified_schema,
            proxies=proxies,
        )

        mappings = map_field_ids(schema, result)
        modified_validations = modify_validations(
            get_validations(
                target_project_id, target_token, target_host_url, proxies=proxies
            ),
            validations,
            target_project_id,
            target_token,
            target_host_url,
            sanitized_udfs,
            mappings,
        )
        for payload in modified_validations:
            result = post_validations(
                target_project_id,
                target_token,
                target_host_url,
                payload,
                proxies=proxies,
            )
            if payload.get("type") == "PROMPT_UDF":
                run_prompt_udf(
                    target_project_id,
                    target_token,
                    target_host_url,
                    result["id"],
                    proxies=proxies,
                )
        return target_project_id

    except Exception as e:
        raise Exception(f"Something went wrong while rebuilding your project: {e}.")


def is_directory(ib_host, api_token, path, proxies=None):
    try:
        contents = list_directory(ib_host, path, api_token, proxies=proxies)
        return True if contents else False
    except Exception as e:
        raise Exception(f"Failed to list directory {path}: {e}")


def download_regression_output(url, api_token, test_summary_path, proxies=None):
    """
    Downloads regression test outputs for applications that have passed the tests.

    Args:
        url (str): The base URL for the API.
        api_token (str): The API token for authentication.
        test_summary_path (str): Path to the test summary file.

    Returns:
        None
    """
    try:
        summary_data = load_from_file(test_summary_path)
    except Exception as e:
        raise Exception(f"Failed to load summary file: {e}")

    for app_name, app_data in summary_data.items():
        summary_path = app_data.get("Summary_Path", "")
        if not summary_path:
            print(f"No summary path found for {app_name}. Skipping download.")
            continue

        folder_path = os.path.dirname(summary_path)
        print(f"Listing files in the folder: {folder_path}")

        try:
            file_list = list_directory(url, folder_path, api_token, proxies=proxies)
        except Exception as e:
            raise Exception(f"Failed to list directory {folder_path}: {e}")

        regression_output_dir = "regression_output"
        os.makedirs(regression_output_dir, exist_ok=True)

        for file_path in file_list:
            print(f"Processing file: {file_path}")
            if is_directory(url, api_token, file_path, proxies=proxies):
                print(f"Skipping directory: {file_path}")
                continue

            try:
                response = read_file_through_api(
                    url, api_token, file_path, proxies=proxies
                )
                response.raise_for_status()
                file_name = os.path.join(
                    regression_output_dir, os.path.basename(file_path)
                )
                with open(file_name, "wb") as f:
                    f.write(response.content)
                print(f"Downloaded file: {file_name}")
            except Exception as e:
                raise Exception(f"Failed to download file {file_path}: {e}")

        test_status = app_data.get("Test_Status", "").lower()
        if test_status != "passed":
            raise Exception(
                f"Regression tests for {app_name} did not pass. Halting further operations."
            )
        print(f"Regression tests for {app_name} passed.")


def run_regression_tests(
    source_host_url,
    source_token,
    source_org,
    source_workspace,
    app_id,
    config,
    proxies=None,
):
    """
    Run regression tests and handle the suite download, upload, and execution.

    Args:
        source_host_url (str): The source host URL.
        source_token (str): The source API token.
        source_org (str): The source organization.
        source_workspace (str): The source workspace.
        app_id (str): The application ID.
        config (dict): The configuration dictionary.

    Returns:
        None
    """
    print("Downloading regression suite...")
    download_regression_suite(proxies=proxies)

    print("Uploading regression suite...")
    target_path = f"{source_org}/{source_workspace}/fs/Instabase Drive/CICD"
    with open("Regression Suite.zip", "rb") as upload_data:
        upload_file(
            source_host_url,
            source_token,
            os.path.join(target_path, "Regression Suite.zip"),
            upload_data,
            proxies=proxies,
        )
    time.sleep(3)
    unzip_files(
        source_host_url,
        source_token,
        os.path.join(target_path, "Regression Suite.zip"),
        target_path,
        proxies=proxies,
    )
    time.sleep(3)
    delete_folder_or_file_from_ib(
        os.path.join(target_path, "Regression Suite.zip"),
        source_host_url,
        source_token,
        use_clients=False,
        proxies=proxies,
    )

    # Uploading the config
    app_config = config["regression"]
    app_config["OUT_FILES_PATH"] = os.path.join(target_path, "regression_output")
    config_path = os.path.join(target_path, "Regression Suite", "app_config.json")
    upload_file(
        source_host_url,
        source_token,
        config_path,
        json.dumps(app_config).encode("utf-8"),
        proxies=proxies,
    )

    print("Running regression...")
    flow_path = os.path.join(
        target_path,
        "Regression Suite",
        "Regression Test Runner v2",
        "regression_test_runner.ibflow",
    )
    input_files_path = os.path.join(
        target_path,
        "Regression Suite",
        "Regression Test Runner v2",
        "datasets",
        "dummy_input",
    )
    create_folder_if_it_does_not_exists(
        source_host_url, source_token, input_files_path, proxies=proxies
    )
    upload_file(
        source_host_url,
        source_token,
        os.path.join(input_files_path, "foot.txt"),
        "dummy_input",
        proxies=proxies,
    )

    flow_config = {
        "APP_ID": app_id,
        "TOKEN": source_token,
        "ENV": source_host_url,
        "TESTS_SUMMARY_PATH": os.path.join(target_path, "summary", "summary.json"),
        "APP_CONFIG_FILE": config_path,
    }

    response = trigger_regression_run(
        source_host_url,
        source_token,
        flow_path,
        flow_config,
        input_files_path,
        proxies=proxies,
    )
    wait_until_job_finishes(
        source_host_url, response, "async", source_token, proxies=proxies
    )
    test_summary_path = flow_config["TESTS_SUMMARY_PATH"]
    print("Downloading test summary...")
    download_file(source_host_url, source_token, test_summary_path, proxies=proxies)
    download_regression_output(
        source_host_url, source_token, "summary.json", proxies=proxies
    )


def main(args=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--compile_solution", action="store_true")
    parser.add_argument("--download_solution", action="store_true")
    parser.add_argument("--publish_build_app", action="store_true")
    parser.add_argument("--create_deployment", action="store_true")
    parser.add_argument("--rebuild", action="store_true")
    parser.add_argument("--create_build_project", action="store_true")
    parser.add_argument("--delete_build", action="store_true")
    parser.add_argument("--regression", action="store_true")
    parser.add_argument("--delete_app", action="store_true")
    if args is not None:
        args = parser.parse_args(args)
    else:
        args = parser.parse_args()

    target_project_id = None
    new_app_id = None

    try:
        config = load_config("config.json")
        source = config["source"]
        target = config["target"]

        # Extract source config
        source_host_url = os.environ.get("SOURCE_HOST_URL")
        if not source_host_url:
            raise ValueError(
                "We couldn't find the source host URL. Please make sure it's set in your environment variables."
            )

        source_token = os.environ.get("SOURCE_TOKEN")
        if not source_token:
            raise ValueError(
                "We couldn't find your source access token. Please make sure it's set in your environment variables."
            )

        project_id = source["project_id"]
        if not project_id:
            raise ValueError(
                "We couldn't find your project ID in the configuration. Please add it to your config.json file."
            )

        source_org = source["org"]
        if not source_org:
            raise ValueError(
                "We couldn't find your source organization in the configuration. Please add it to your config.json file."
            )

        source_workspace = source["workspace"]
        if not source_workspace:
            raise ValueError(
                "We couldn't find your source workspace in the configuration. Please add it to your config.json file."
            )

        app_id = source.get("app_id")
        deployment_id = source.get("deployment_id")

        # Extract target config
        target_host_url = os.environ.get("TARGET_HOST_URL")
        if not target_host_url:
            raise ValueError(
                "We couldn't find the target host URL. Please make sure it's set in your environment variables."
            )

        target_token = os.environ.get("TARGET_TOKEN")
        if not target_token:
            raise ValueError(
                "We couldn't find your target access token. Please make sure it's set in your environment variables."
            )

        target_org = target["org"]
        if not target_org:
            raise ValueError(
                "We couldn't find your target organization in the configuration. Please add it to your config.json file."
            )

        target_workspace = target["workspace"]
        if not target_workspace:
            raise ValueError(
                "We couldn't find your target workspace in the configuration. Please add it to your config.json file."
            )

        if (
            os.environ.get("PROXY_HOST")
            and os.environ.get("PROXY_USER")
            and os.environ.get("PROXY_PASSWORD")
            and os.environ.get("PROXY_PORT")
        ):
            proxy = {
                "http": f"http://{os.environ.get('PROXY_USER')}:{os.environ.get('PROXY_PASSWORD')}@{os.environ.get('PROXY_HOST')}:{os.environ.get('PROXY_PORT')}",
                "https": f"http://{os.environ.get('PROXY_USER')}:{os.environ.get('PROXY_PASSWORD')}@{os.environ.get('PROXY_HOST')}:{os.environ.get('PROXY_PORT')}",
            }
        else:
            print(
                "No proxy found in the environment variables. Using direct connection."
            )
            proxy = None

        if args.compile_solution:
            print("Compiling solution binary...")
            response = generate_flow(
                source_host_url, source_token, project_id, source_org, proxies=proxy
            )
            print(response)
            job_id = response["job_id"]
            response = wait_until_job_finishes(
                source_host_url, job_id, "async", source_token, proxies=proxy
            )
            print(response)
            solution_path = response["results"][0]["flow_path"]

        if args.download_solution:
            data_path = os.path.join(
                "/".join(solution_path.split("/")[0:-1]), "project_snapshot.json"
            )

            print("Downloading project snapshot...")
            download_file(source_host_url, source_token, data_path, proxies=proxy)

            print("Fetching schema details for rebuilding...")
            fetch_details(config, proxies=proxy)

            if app_id:
                print("Getting app details...")
                response = get_app_details(
                    source_host_url, source_token, source_org, app_id, proxies=proxy
                )
                details = response.get("solution", {})
                if not details:
                    raise Exception(
                        "We couldn't find any information about this app. Please verify that you've entered the correct app ID in your configuration and try again."
                    )
                save_to_file(details, "app_details.json")

                # Download app icon if solution path exists
                if details.get("solution_path"):
                    print("Downloading app icon...")
                    try:
                        icon_data = read_file_through_api(
                            source_host_url,
                            source_token,
                            details["solution_path"] + "/icon.png",
                            proxies=proxy,
                        ).content
                    except Exception as e:
                        print(f"Failed to download app icon: {e}")
                        icon_data = read_image()

                    with open("icon.png", "wb") as f:
                        f.write(icon_data)
            elif source.get("app_details"):
                print("No app ID found. Using app details to create an app.")
                app_details = source.get("app_details")
                print("Publishing build app...")
                payload = {
                    "proj_uuid": project_id,
                    "app_detail": {
                        "name": app_details["name"],
                        "version": app_details["version"],
                        "description": app_details["description"],
                        "visibility": "PRIVATE",
                        "release_notes": app_details["release_notes"],
                        "billing_model": "default",
                        "update_mode": "AUTO_UPDATE",
                    },
                    "ibflow_path": solution_path,
                    "should_copy_snapshot": True,
                }
                print(payload)
                # Publish the build app
                response = publish_build_app(
                    source_host_url, source_token, payload, source_org, proxies=proxy
                )
                response = wait_until_job_finishes(
                    source_host_url,
                    response["job_id"],
                    "async",
                    source_token,
                    proxies=proxy,
                )
                print(response)
                new_app_id = get_published_app_id(
                    source_host_url, source_token, project_id, proxies=proxy
                )
                config["source"]["app_id"] = new_app_id
                save_to_file(config, "config.json")
                print("Getting app details...")
                response = get_app_details(
                    source_host_url, source_token, source_org, new_app_id, proxies=proxy
                )
                details = response.get("solution", {})
                if not details:
                    raise Exception(
                        "We couldn't find any information about this app. Please verify that you've entered the correct app ID in your configuration and try again."
                    )
                save_to_file(details, "app_details.json")

                # Download app icon if solution path exists
                if details.get("solution_path"):
                    print("Downloading app icon...")
                    try:
                        icon_data = read_file_through_api(
                            source_host_url,
                            source_token,
                            details["solution_path"] + "/icon.png",
                            proxies=proxy,
                        ).content
                    except Exception as e:
                        print(f"Failed to download app icon: {e}")
                        icon_data = read_image()

                    with open("icon.png", "wb") as f:
                        f.write(icon_data)
            else:
                print("No app ID or app details found.")

            if deployment_id:
                print("Getting deployment details...")
                response = get_deployment_details(
                    source_host_url,
                    source_token,
                    source_org,
                    deployment_id,
                    proxies=proxy,
                )
                save_to_file(response, "deployment_details.json")

        if args.regression:
            run_regression_tests(
                source_host_url,
                source_token,
                source_org,
                source_workspace,
                app_id,
                config,
                proxies=proxy,
            )

        if args.create_build_project:
            print("Creating build project...")
            target_project_id = rebuild_project(config, proxies=proxy)
            print(f"Build project created successfully with ID: {target_project_id}")

        if args.publish_build_app:
            if not app_id:
                raise Exception(
                    "We couldn't find your app ID in the configuration. Please add it to your config.json file under source.app_id"
                )

            target_project_id = config["target"].get("project_id")

            # it is to support older version (can remove this in future)
            if not target_project_id:
                target_project_id = rebuild_project(config, proxies=proxy)
                print(
                    f"Build project created successfully with ID: {target_project_id}"
                )

            time.sleep(10)
            response = generate_flow(
                target_host_url,
                target_token,
                target_project_id,
                target_org,
                "icon.png",
                proxies=proxy,
            )
            print(response)
            job_id = response["job_id"]
            response = wait_until_job_finishes(
                target_host_url, job_id, "async", target_token, proxies=proxy
            )
            print(response)
            time.sleep(3)
            app_details = load_from_file("app_details.json")
            solution_path = response["results"][0]["flow_path"]

            print("Publishing build app...")
            payload = {
                "proj_uuid": target_project_id,
                "app_detail": {
                    "name": app_details["name"],
                    "version": app_details["version"],
                    "description": app_details["summary"],
                    "visibility": app_details["visibility"],
                    "release_notes": app_details["description"],
                    "billing_model": "default",
                    "update_mode": app_details["updateMode"],
                },
                "ibflow_path": solution_path,
                "should_copy_snapshot": True,
            }
            print(payload)
            # Publish the build app
            response = publish_build_app(
                target_host_url, target_token, payload, target_org, proxies=proxy
            )
            response = wait_until_job_finishes(
                target_host_url,
                response["job_id"],
                "async",
                target_token,
                proxies=proxy,
            )
            print(response)
            new_app_id = get_published_app_id(
                target_host_url, target_token, target_project_id, proxies=proxy
            )

            # Add the state to the app
            payload = {
                "is_customizable": app_details["isCustomizable"],
                "state": app_details["state"],
            }
            response = add_the_state(
                target_host_url,
                target_token,
                payload,
                target_org,
                new_app_id,
                proxies=proxy,
            )
            print(response)

            config["target"]["app_id"] = new_app_id
            save_to_file(config, "config.json")
            print("Great news! Your app has been published successfully.")

        if (args.create_build_project or args.publish_build_app) and not args.rebuild:
            if target_project_id:
                print(
                    f"Deleting build project with ID as rebuild is false: {target_project_id}..."
                )
                delete_build_project(
                    target_host_url, target_token, target_project_id, proxies=proxy
                )
                print("Build project deleted successfully.")
            else:
                raise Exception("No build project ID found to delete.")

        if args.create_deployment:
            new_app_id = config["target"].get("app_id")
            if not new_app_id:
                raise Exception("Couldn't find the app ID.")
            if not deployment_id:
                raise Exception(
                    "We couldn't find your deployment ID in the configuration. Please add it to your config.json file under source.deployment_id"
                )

            details = load_from_file("deployment_details.json")
            print("Creating deployment...")
            deployment_id = config["target"].get("deployment_id")
            payload = {
                "name": details["name"],
                "workspace": target_workspace,
                "deployed_solution_id": new_app_id,
                "description": details["description"],
                "human_review_mode": details["human_review_mode"],
                "human_review_level": details["human_review_level"],
            }
            create_deployment(
                target_host_url,
                target_token,
                payload,
                target_org,
                deployment_id,
                proxies=proxy,
            )
            print("Great news! Your deployment has been created successfully.")

        if args.delete_build:
            target_project_id = config["target"].get("project_id")
            if target_project_id:
                delete_build_project(
                    target_host_url, target_token, target_project_id, proxies=proxy
                )
                print("Build project deleted successfully.")

        if args.delete_app:
            if new_app_id:
                delete_app(
                    target_host_url, target_token, new_app_id, target_org, proxies=proxy
                )
                print("App deleted successfully.")

    except Exception as e:
        print(f"Something unexpected went wrong: {str(e)}.")
        raise


if __name__ == "__main__":
    main()
