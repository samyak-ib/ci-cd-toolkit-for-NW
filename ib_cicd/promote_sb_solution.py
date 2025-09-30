import argparse
import json
import os
import pathlib
import re
import time

from ib_cicd.ib_helpers import (
    check_job_status_build,
    compile_solution,
    copy_file_within_ib,
    create_deployment,
    delete_folder_or_file_from_ib,
    get_app_details,
    get_deployment_details,
    list_directory,
    publish_advanced_app,
    read_file_through_api,
    unzip_files,
    upload_file,
    delete_app,
    read_image,
)
from ib_cicd.migration_helpers import (
    download_dependencies_from_dev_and_upload_to_prod,
    download_solution,
    publish_dependencies,
)
from ib_cicd.promote_build_solution import (
    load_config,
    load_from_file,
    read_binary,
    save_to_file,
    run_regression_tests,
)
from ib_cicd.promote_solution import (
    get_latest_binary_path,
    parse_dependencies,
    upload_zip_to_instabase,
    version_tuple,
)


def get_latest_flow_version(flow_path, ib_host, ib_token):
    """Get latest version number from flow directory.

    Args:
        flow_path: IB path to directory with versioned flows
        ib_host: IB host URL
        ib_token: IB API token

    Returns:
        Latest version in major.minor.patch format
    """
    latest_version = "0.0.0"
    try:
        paths = list_directory(ib_host, flow_path, ib_token)
        versions = []
        for path in paths:
            p = pathlib.Path(path)
            if re.fullmatch(r"\d+\.\d+\.\d+", p.stem):
                versions.append(p.stem)

        if versions:
            # Sort versions using version_tuple to properly compare semantic versions
            versions.sort(key=version_tuple)
            latest_version = versions[-1]

        return latest_version

    except Exception as e:
        print(
            f"Unable to determine the latest version of your flow. This may be because the flow directory is empty or inaccessible. Error details: {e}"
        )
        raise


def get_sb_flow_path(solution_builder_name, flow_name, ib_root, ib_host, ib_token):
    """Get path to flow in solution builder project.

    Args:
        solution_builder_name: Name of solution builder project
        flow_name: Name of flow to find
        ib_root: Root IB drive path
        ib_host: IB host URL
        ib_token: IB API token

    Returns:
        Full IB path to flow version

    Raises:
        FileNotFoundError: If flow not found
        Exception: For other errors
    """
    flows_path = os.path.join(
        ib_root, ".instabase_projects", solution_builder_name, "latest", "flows"
    )
    try:
        paths = list_directory(ib_host, flows_path, ib_token)
        for path in paths:
            metadata_path = os.path.join(path, "metadata.json")
            metadata_content = read_file_through_api(
                ib_host, ib_token, metadata_path
            ).content
            metadata = json.loads(metadata_content)
            if metadata["name"] == flow_name:
                flow_version = metadata["versions_tree"]["version_id"]
                return os.path.join(path, "versions", flow_version)
        raise FileNotFoundError(
            f"We couldn't find a flow named '{flow_name}' in your Solution Builder project. Please verify that you've entered the correct flow name in your configuration."
        )
    except Exception as e:
        print(
            f"We encountered an issue while trying to locate your flow. This could be due to incorrect project settings or permission issues. Please check your configuration and try again. Error details: {e}"
        )
        raise


def main(args=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--compile_solution", action="store_true")
    parser.add_argument("--promote_solution_to_target", action="store_true")
    parser.add_argument("--upload_dependencies", action="store_true")
    parser.add_argument("--download_solution", action="store_true")
    parser.add_argument("--publish_advanced_app", action="store_true")
    parser.add_argument("--create_deployment", action="store_true")
    parser.add_argument("--delete_app", action="store_true")
    parser.add_argument("--regression", action="store_true")
    if args is not None:
        args = parser.parse_args(args)
    else:
        args = parser.parse_args()

    new_app_id = None
    try:
        # Load configuration
        config = load_config("config.json")

        # Source environment config
        SOURCE_IB_HOST = os.environ.get("SOURCE_HOST_URL")
        SOURCE_IB_API_TOKEN = os.environ.get("SOURCE_TOKEN")
        SOLUTION_BUILDER_NAME = config["source"].get("sb_name")
        FLOW_NAME = config["source"].get("flow_name")
        app_id = config["source"].get("app_id")
        deployment_id = config["source"].get("deployment_id")
        SOURCE_ORG = config["source"].get("org")
        SOURCE_WORKSPACE = config["source"].get("workspace")
        WORKSPACE_DRIVE_PATH = (
            f"{SOURCE_ORG}/{SOURCE_WORKSPACE}/fs/Instabase Drive"
            if SOURCE_ORG and SOURCE_WORKSPACE
            else None
        )
        SOURCE_WORKING_DIR = (
            f"{WORKSPACE_DRIVE_PATH}/CICD" if WORKSPACE_DRIVE_PATH else None
        )

        # Target environment config
        TARGET_IB_HOST = os.environ.get("TARGET_HOST_URL")
        TARGET_IB_API_TOKEN = os.environ.get("TARGET_TOKEN")
        TARGET_ORG = config["target"].get("org")
        TARGET_WORKSPACE = config["target"].get("workspace")
        TARGET_IB_PATH = (
            f"{TARGET_ORG}/{TARGET_WORKSPACE}/fs/Instabase Drive/CICD"
            if TARGET_ORG and TARGET_WORKSPACE
            else None
        )

        if args.compile_solution:
            flow_folder = get_sb_flow_path(
                SOLUTION_BUILDER_NAME,
                FLOW_NAME,
                WORKSPACE_DRIVE_PATH,
                SOURCE_IB_HOST,
                SOURCE_IB_API_TOKEN,
            )
            flow_path = os.path.join(flow_folder, "flow.ibflow")
            flow_builds_dir = os.path.join(os.path.dirname(flow_path), "builds")

            current_version = version_tuple(
                get_latest_flow_version(
                    flow_builds_dir, SOURCE_IB_HOST, SOURCE_IB_API_TOKEN
                )
            )
            version = (
                f"{current_version[0]}.{current_version[1]}.{current_version[2] + 1}"
            )

            compile_solution(
                SOURCE_IB_HOST,
                SOURCE_IB_API_TOKEN,
                flow_path,
                solution_builder=True,
                solution_version=version,
            )
            time.sleep(3)

            flow_binary_path = os.path.join(flow_builds_dir, f"{version}.ibflowbin")
            copy_file_within_ib(
                SOURCE_IB_HOST,
                SOURCE_IB_API_TOKEN,
                flow_binary_path,
                os.path.join(SOURCE_WORKING_DIR, f"{version}.ibflowbin"),
            )
            time.sleep(3)
            delete_folder_or_file_from_ib(
                flow_binary_path, SOURCE_IB_HOST, SOURCE_IB_API_TOKEN, use_clients=False
            )

        if args.download_solution:
            binary_path = get_latest_binary_path(
                SOURCE_IB_API_TOKEN, SOURCE_IB_HOST, SOURCE_WORKING_DIR
            )
            download_solution(SOURCE_IB_HOST, SOURCE_IB_API_TOKEN, binary_path)
            time.sleep(2)
            delete_folder_or_file_from_ib(
                SOURCE_WORKING_DIR,
                SOURCE_IB_HOST,
                SOURCE_IB_API_TOKEN,
                use_clients=False,
            )

            if app_id:
                print("Getting app details...")
                response = get_app_details(
                    SOURCE_IB_HOST, SOURCE_IB_API_TOKEN, SOURCE_ORG, app_id
                )
                details = response.get("solution", {})
                if not details:
                    raise ValueError(
                        "We couldn't find any information about this app. Please verify that you've entered the correct app ID in your configuration and try again."
                    )
                save_to_file(details, "app_details.json")

                # Download app icon if solution path exists
                if details.get("solution_path"):
                    print("Downloading app icon...")
                    try:
                        icon_data = read_file_through_api(
                            SOURCE_IB_HOST,
                            SOURCE_IB_API_TOKEN,
                            details["solution_path"] + "/icon.png",
                        ).content
                    except Exception as e:
                        print(f"Failed to download app icon: {e}")
                        icon_data = read_image()

                    with open("icon.png", "wb") as f:
                        f.write(icon_data)

            if deployment_id:
                print("Getting deployment details...")
                response = get_deployment_details(
                    SOURCE_IB_HOST, SOURCE_IB_API_TOKEN, SOURCE_ORG, deployment_id
                )
                save_to_file(response, "deployment_details.json")

        if args.regression:
            run_regression_tests(
                SOURCE_IB_HOST,
                SOURCE_IB_API_TOKEN,
                SOURCE_ORG,
                SOURCE_WORKSPACE,
                app_id,
                config,
            )

        if args.promote_solution_to_target:
            upload_zip_to_instabase(
                TARGET_IB_PATH,
                TARGET_IB_HOST,
                TARGET_IB_API_TOKEN,
                SOLUTION_BUILDER_NAME,
            )

            # Upload the solution binary to target environment
            target_binary_path = os.path.join(
                TARGET_IB_PATH,
                SOLUTION_BUILDER_NAME,
                f"{SOLUTION_BUILDER_NAME}.ibflowbin",
            )
            binary_content = read_binary("solution.ibflowbin")
            upload_file(
                TARGET_IB_HOST, TARGET_IB_API_TOKEN, target_binary_path, binary_content
            )
            time.sleep(2)

            # Unzip solution contents
            zip_path = os.path.join(TARGET_IB_PATH, f"{SOLUTION_BUILDER_NAME}.zip")
            unzip_files(TARGET_IB_HOST, TARGET_IB_API_TOKEN, zip_path)
            time.sleep(3)
            delete_folder_or_file_from_ib(
                zip_path, TARGET_IB_HOST, TARGET_IB_API_TOKEN, use_clients=False
            )

        if args.upload_dependencies:
            dependencies = config["source"].get("dependencies", [])
            requirements_dict = parse_dependencies(dependencies)

            if requirements_dict:
                uploaded_ibsolutions = (
                    download_dependencies_from_dev_and_upload_to_prod(
                        SOURCE_IB_HOST,
                        TARGET_IB_HOST,
                        SOURCE_IB_API_TOKEN,
                        TARGET_IB_API_TOKEN,
                        SOURCE_WORKING_DIR,
                        TARGET_IB_PATH,
                        requirements_dict,
                    )
                )
                publish_dependencies(
                    uploaded_ibsolutions, TARGET_IB_HOST, TARGET_IB_API_TOKEN
                )
            else:
                print(
                    "No additional components need to be uploaded - your solution is self-contained."
                )

        if args.publish_advanced_app:
            if not app_id:
                raise ValueError(
                    "We couldn't find the app ID in your configuration. Please add the source app ID to your config.json file and try again."
                )

            app_details = load_from_file("app_details.json")
            icon_path = os.path.join(TARGET_IB_PATH, SOLUTION_BUILDER_NAME, "icon.png")

            # Upload the locally saved icon
            if os.path.exists("icon.png"):
                print("Uploading app icon from local file...")
                with open("icon.png", "rb") as f:
                    icon_data = f.read()
                upload_file(TARGET_IB_HOST, TARGET_IB_API_TOKEN, icon_path, icon_data)
            else:
                print("Local icon file not found. Skipping icon upload.")

            print("Publishing the advanced app...")
            ibflowbin_path = get_latest_binary_path(
                TARGET_IB_API_TOKEN,
                TARGET_IB_HOST,
                os.path.join(TARGET_IB_PATH, SOLUTION_BUILDER_NAME),
            )

            payload = {
                "ibflowbin_path": ibflowbin_path,
                "icon_path": icon_path,
                "app_detail": {
                    "name": app_details["name"],
                    "version": app_details["version"],
                    "description": app_details["summary"],
                    "visibility": app_details.get("visibility", "PRIVATE"),
                    "release_notes": app_details["description"],
                    "billing_model": "default",
                },
            }

            response = publish_advanced_app(
                TARGET_IB_HOST, TARGET_IB_API_TOKEN, payload, TARGET_ORG
            )
            new_app_id = check_job_status_build(
                TARGET_IB_HOST, TARGET_IB_API_TOKEN, response["job_id"]
            )
            config["target"]["app_id"] = new_app_id
            save_to_file(config, "config.json")
            print(
                "Great news! Your app has been successfully published. The new app ID is: %s",
                new_app_id,
            )

        if args.create_deployment:
            if not deployment_id:
                raise ValueError(
                    "We couldn't find the deployment ID in your configuration. Please add the source deployment ID to your config.json file and try again."
                )

            new_app_id = config["target"].get("app_id")
            if not new_app_id:
                raise Exception("Couldn't find the app ID.")

            details = load_from_file("deployment_details.json")

            print("Creating the deployment...")
            payload = {
                "name": details["name"],
                "workspace": TARGET_WORKSPACE,
                "deployed_solution_id": new_app_id,
                "description": details["description"],
                "human_review_mode": details["human_review_mode"],
                "human_review_level": details["human_review_level"],
            }
            create_deployment(TARGET_IB_HOST, TARGET_IB_API_TOKEN, payload, TARGET_ORG)
            print("Success! Your deployment has been created and is ready to use.")

        if args.delete_app:
            if not new_app_id:
                raise ValueError(
                    "We couldn't find the app ID in your configuration. Please add the source app ID to your config.json file and try again."
                )

            print(f"Deleting app with ID: {new_app_id}...")
            delete_app(TARGET_IB_HOST, TARGET_IB_API_TOKEN, new_app_id, TARGET_ORG)
            print("App deleted successfully.")

    except Exception as e:
        print(f"Something unexpected went wrong: {str(e)}.")
        raise


if __name__ == "__main__":
    main()
