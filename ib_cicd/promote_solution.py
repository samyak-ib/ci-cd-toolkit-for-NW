import argparse
import os
import re
import shutil
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
    read_image,
    delete_app,
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


def copy_solution_to_working_dir(
    source_host, source_token, source_dir, rel_flow_path, new_solution_dir
):
    """Copy solution files to working directory.

    Args:
        source_host: Source Instabase host
        source_token: Source API token
        source_dir: Source directory path
        rel_flow_path: Relative flow path
        new_solution_dir: New solution directory path
    """
    flow_path = os.path.join(source_dir, rel_flow_path)
    modules_path = os.path.join(source_dir, *rel_flow_path.split("/")[:-1], "modules")
    for path in [flow_path, modules_path]:
        new_path = path.replace(source_dir, new_solution_dir)
        copy_file_within_ib(
            source_host, source_token, path, new_path, use_clients=False
        )


def upload_zip_to_instabase(target_path, target_host, target_token, solution_name):
    """Create and upload solution zip archive to Instabase.

    Args:
        target_path: Target Instabase path
        target_host: Target Instabase host
        target_token: Target API token
        solution_name: Name of solution

    Returns:
        Upload response from API

    Raises:
        Exception: If zip creation or upload fails
    """
    try:
        shutil.make_archive("solution", "zip", "solution")
        path_to_upload = os.path.join(target_path, f"{solution_name}.zip")

        with open("solution.zip", "rb") as upload_data:
            return upload_file(target_host, target_token, path_to_upload, upload_data)
    except Exception as e:
        print(
            f"We couldn't upload your solution package. This could be because of internet connectivity issues or the system may be temporarily unavailable. Please check your internet connection and try again. If the problem continues, contact your IT support team. {e}"
        )
        raise e


def version_tuple(v):
    """Convert version string to tuple of integers.

    Args:
        v: Version string in format "x.y.z"

    Returns:
        Tuple of version integers
    """
    return tuple(map(int, (v.split("."))))


def get_latest_binary_path(api_token, ib_host, solution_path):
    """Get path of latest versioned .ibflowbin file.
    If no versioned binary found, return path of simple named binary if exists.

    Args:
        api_token: API token
        ib_host: Instabase host
        solution_path: Path to search for binaries

    Returns:
        Path to latest binary file or simple named binary file

    Raises:
        Exception: If no valid binaries found
    """
    paths = list_directory(ib_host, solution_path, api_token)
    paths = [p for p in paths if p.endswith(".ibflowbin")]
    if not paths:
        raise Exception(
            f"We couldn't find any solution files at {solution_path}. Please double-check that you've entered the correct location for your solution and try again."
        )

    versioned_binaries = []
    simple_binaries = []

    for path in paths:
        filename = os.path.basename(path)
        version = filename.replace(".ibflowbin", "")
        if re.fullmatch(r"\d+\.\d+\.\d+", version):
            versioned_binaries.append(path)
        else:
            simple_binaries.append(path)

    if versioned_binaries:
        latest_version = "0.0.0"
        latest_path = None
        for path in versioned_binaries:
            filename = os.path.basename(path)
            version = filename.replace(".ibflowbin", "")
            if version_tuple(version) > version_tuple(latest_version):
                latest_version = version
                latest_path = path
        return latest_path
    elif simple_binaries:
        return simple_binaries[0]
    else:
        raise Exception(
            "We couldn't find any valid solution files. This usually means the solution hasn't been compiled properly. Please make sure you've completed the compilation step before proceeding."
        )


def parse_dependencies(dependencies):
    """Parse dependency string into dictionary.

    Args:
        dependencies: List of dependencies in format ["name==version"]

    Returns:
        Dictionary mapping dependency names to versions
    """
    if not dependencies:
        return {}
    try:
        return {
            m.split("==")[0].strip(): m.split("==")[1].strip()
            for m in dependencies
            if "==" in m
        }
    except Exception as e:
        print(
            f"There seems to be an issue with the dependencies list. Each dependency should be written as 'name==version' (for example, 'my-package==1.0.0'). Please check your list and fix any formatting issues. {e}"
        )
        raise e


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
        source_config = config["source"]
        SOURCE_IB_HOST = os.environ.get("SOURCE_HOST_URL")
        SOURCE_IB_API_TOKEN = os.environ.get("SOURCE_TOKEN")
        FLOW_PATH = source_config.get("flow_path")
        app_id = source_config.get("app_id")
        deployment_id = source_config.get("deployment_id")
        SOURCE_ORG = source_config.get("org")
        SOURCE_WORKSPACE = source_config.get("workspace")

        if FLOW_PATH:
            SOURCE_SOLUTION_DIR = "/".join(FLOW_PATH.split("/")[:-1])
            REL_FLOW_PATH = FLOW_PATH.split("/")[-1]
            SOURCE_WORKING_DIR = os.path.join(
                SOURCE_SOLUTION_DIR, "CICD", SOURCE_SOLUTION_DIR.split("/")[-1]
            )
            FLOW_NAME = REL_FLOW_PATH.split(".")[0]
        else:
            SOURCE_SOLUTION_DIR = None
            REL_FLOW_PATH = None
            SOURCE_WORKING_DIR = None
            FLOW_NAME = None

        # Target environment config
        target_config = config["target"]
        TARGET_IB_HOST = os.environ.get("TARGET_HOST_URL")
        TARGET_IB_API_TOKEN = os.environ.get("TARGET_TOKEN")
        TARGET_ORG = target_config.get("org")
        TARGET_WORKSPACE = target_config.get("workspace")
        TARGET_IB_PATH = (
            f"{TARGET_ORG}/{TARGET_WORKSPACE}/fs/Instabase Drive/CICD"
            if TARGET_ORG and TARGET_WORKSPACE
            else None
        )

        if args.compile_solution:
            copy_solution_to_working_dir(
                SOURCE_IB_HOST,
                SOURCE_IB_API_TOKEN,
                SOURCE_SOLUTION_DIR,
                REL_FLOW_PATH,
                SOURCE_WORKING_DIR,
            )
            time.sleep(3)
            compile_solution(
                SOURCE_IB_HOST,
                SOURCE_IB_API_TOKEN,
                SOURCE_WORKING_DIR,
                REL_FLOW_PATH,
            )
            time.sleep(3)

        if args.download_solution:
            binary_path = get_latest_binary_path(
                SOURCE_IB_API_TOKEN, SOURCE_IB_HOST, SOURCE_WORKING_DIR
            )
            download_solution(SOURCE_IB_HOST, SOURCE_IB_API_TOKEN, binary_path)
            time.sleep(2)
            delete_folder_or_file_from_ib(
                os.path.join(SOURCE_SOLUTION_DIR, "CICD"),
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
                    print(
                        "We couldn't find any information about this app. Please verify that you've entered the correct app ID in your configuration and try again."
                    )
                    raise Exception("App details not found.")
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
                TARGET_IB_PATH, TARGET_IB_HOST, TARGET_IB_API_TOKEN, FLOW_NAME
            )

            # Upload the solution binary to target environment
            target_binary_path = os.path.join(
                TARGET_IB_PATH, FLOW_NAME, f"{FLOW_NAME}.ibflowbin"
            )
            binary_content = read_binary("solution.ibflowbin")
            upload_file(
                TARGET_IB_HOST,
                TARGET_IB_API_TOKEN,
                target_binary_path,
                binary_content,
            )
            time.sleep(2)

            # Unzip solution contents
            zip_path = os.path.join(TARGET_IB_PATH, f"{FLOW_NAME}.zip")
            unzip_files(TARGET_IB_HOST, TARGET_IB_API_TOKEN, zip_path)
            time.sleep(3)
            delete_folder_or_file_from_ib(
                zip_path, TARGET_IB_HOST, TARGET_IB_API_TOKEN, use_clients=False
            )

        if args.upload_dependencies:
            dependencies = config["source"].get("dependencies", [])
            requirements_dict = parse_dependencies(dependencies)

            uploaded_ibsolutions = download_dependencies_from_dev_and_upload_to_prod(
                SOURCE_IB_HOST,
                TARGET_IB_HOST,
                SOURCE_IB_API_TOKEN,
                TARGET_IB_API_TOKEN,
                SOURCE_WORKING_DIR,
                TARGET_IB_PATH,
                requirements_dict,
            )
            publish_dependencies(
                uploaded_ibsolutions, TARGET_IB_HOST, TARGET_IB_API_TOKEN
            )

        if args.publish_advanced_app:
            if not app_id:
                print(
                    "We couldn't find an app ID in your configuration. Please add the source app ID to your configuration file and try again."
                )
                raise Exception("App ID not found in configuration.")

            app_details = load_from_file("app_details.json")
            icon_path = os.path.join(TARGET_IB_PATH, FLOW_NAME, "icon.png")

            # Upload the locally saved icon
            if os.path.exists("icon.png"):
                print("Uploading app icon from local file...")
                with open("icon.png", "rb") as f:
                    icon_data = f.read()
                upload_file(TARGET_IB_HOST, TARGET_IB_API_TOKEN, icon_path, icon_data)
            else:
                print("Local icon file not found.")
                raise FileNotFoundError("Icon file not found.")

            print("Publishing the advanced app...")
            ibflowbin_path = get_latest_binary_path(
                TARGET_IB_API_TOKEN,
                TARGET_IB_HOST,
                os.path.join(TARGET_IB_PATH, FLOW_NAME),
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
            print("Great news! Your app has been published successfully.")

        if args.create_deployment:
            if not deployment_id:
                print(
                    "We couldn't find a deployment ID in your configuration. Please add the source deployment ID to your configuration file and try again."
                )
                raise Exception("Deployment ID not found in configuration.")

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
            print("Great news! Your deployment has been created successfully.")

        if args.delete_app:
            if not new_app_id:
                raise Exception("App ID not found for deletion.")

            delete_app(TARGET_IB_HOST, TARGET_IB_API_TOKEN, new_app_id, TARGET_ORG)
            print("App deleted successfully.")

    except Exception as e:
        print(f"Something unexpected went wrong: {str(e)}.")
        raise


if __name__ == "__main__":
    main()
