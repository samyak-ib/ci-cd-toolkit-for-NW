import os
from pathlib import Path
from zipfile import ZipFile

import requests
from ib_cicd.ib_helpers import (
    create_folder_if_it_does_not_exists,
    get_file_metadata,
    publish_to_marketplace,
    read_file_content_from_ib,
    read_file_through_api,
    upload_chunks,
    wait_until_job_finishes,
)


def download_solution(
    ib_host, api_token, solution_path, write_to_local=True, unzip_solution=True
):
    """Downloads .ibsolution file content.

    Args:
        ib_host: IB host URL.
        api_token: IB API token.
        solution_path: Path to ibsolution on IB.
        write_to_local: Write .ibsolution bytes to local file.
        unzip_solution: Unzip the solution after download.
    Returns:
        Response object.
    """
    resp = read_file_through_api(ib_host, api_token, solution_path)

    if write_to_local:
        with open("solution.ibflowbin", "wb") as fd:
            fd.write(resp.content)

        if unzip_solution:
            zip_path = "solution.zip"
            with open(zip_path, "wb") as fd:
                fd.write(resp.content)
            with ZipFile(zip_path, "r") as zip_ref:
                unzip_dir = Path(zip_path).parent / Path(zip_path).stem
                zip_ref.extractall(unzip_dir)
            os.remove(zip_path)
    return resp


def copy_package_from_marketplace(
    ib_host, api_token, package_name, package_version, intermediate_path
):
    """Copies ibsolution from marketplace to intermediate location and downloads it.

    Args:
        ib_host: IB host URL.
        api_token: IB API token.
        package_name: Marketplace package name.
        package_version: Marketplace package version.
        intermediate_path: Path to copy ibsolution to.
    Returns:
        Intermediate path of copied ibsolution.
    """
    solution_name = f"{package_name}-{package_version}.ibsolution"

    # TODO: Check if file exists
    # Get url to marketplace solution
    dev_marketplace_solution_url = os.path.join(
        ib_host,
        "api/v1/drives/system/global/fs/Instabase%20Drive/Applications/Marketplace/All",
    )
    dev_marketplace_solution_url = os.path.join(
        dev_marketplace_solution_url, package_name, package_version, solution_name
    )

    if not intermediate_path.endswith(solution_name):
        intermediate_path = os.path.join(intermediate_path, solution_name)

    copy_url = os.path.join(dev_marketplace_solution_url, "copy?is_v2=true")
    headers = {"Authorization": f"Bearer {api_token}"}
    params = {"new_full_path": intermediate_path}
    resp = requests.post(copy_url, headers=headers, json=params, verify=False)
    resp.raise_for_status()

    content = resp.json()
    job_id = content["job_id"]
    wait_until_job_finishes(ib_host, job_id, "job", api_token)

    return intermediate_path


def check_if_file_exists_on_ib_env(
    ib_host, api_token, file_path, use_clients=False, **kwargs
):
    """Checks if a file exists on IB environment.

    Uses clients if use_clients is True, otherwise uses Metadata API.

    Args:
        ib_host: IB host URL.
        api_token: IB API token.
        file_path: Path to file on IB.
        use_clients: Use clients if True.
        kwargs: Optional kwargs.
    Returns:
        True if file exists, False otherwise.
    """

    if use_clients:
        # Use clients from kwargs if user sets flag to True
        clients, err = kwargs["_FN_CONTEXT_KEY"].get_by_col_name("CLIENTS")
        return clients.ibfile.is_file(file_path)
    else:
        # Check file metadata and determine if file already exists
        metadata_response = get_file_metadata(ib_host, api_token, file_path)
        if metadata_response.status_code == 200:
            try:
                content_length = int(metadata_response.headers["Content-Length"])
                if content_length > 100000:
                    # File exists
                    return True
            except (KeyError, ValueError):
                pass

    return False


def copy_marketplace_package_and_move_to_new_env(
    source_ib_host,
    target_ib_host,
    package_name,
    package_version,
    source_api_token,
    target_api_token,
    download_folder,
    prod_upload_folder,
    use_clients=False,
    **kwargs,
):
    """Downloads ibsolution from dev marketplace and moves to prod env.

    Args:
        source_ib_host: Source IB host URL.
        target_ib_host: Target IB host URL.
        package_name: Marketplace package name.
        package_version: Marketplace package version.
        source_api_token: Source IB API token.
        target_api_token: Target IB API token.
        download_folder: Intermediate folder on source env.
        prod_upload_folder: Folder on target env to upload to.
        use_clients: Use clients if True.
        kwargs: Optional kwargs.
    Returns:
        Tuple(Response object, str) - Upload chunks response and uploaded file path.
    """
    solution_name = f"{package_name}-{package_version}.ibsolution"
    final_upload_path = os.path.join(prod_upload_folder, solution_name)

    # Check file metadata and determine if file already exists
    metadata_response = get_file_metadata(
        target_ib_host, target_api_token, final_upload_path
    )
    if metadata_response.status_code == 200:
        try:
            content_length = int(metadata_response.headers["Content-Length"])
            if content_length > 100000:
                # File exists
                return None, final_upload_path
        except (KeyError, ValueError):
            pass

    # If file doesn't exist in target env, copy it to a temporary download
    # folder on source env and then move it to target env
    copy_to_path = os.path.join(download_folder, solution_name)

    # Check if file exists in temp download folder on source env, if it
    # doesn't exist then copy it over
    if not check_if_file_exists_on_ib_env(
        source_ib_host, source_api_token, copy_to_path, use_clients, **kwargs
    ):
        copy_package_from_marketplace(
            source_ib_host,
            source_api_token,
            package_name,
            package_version,
            copy_to_path,
        )

    # Download file contents of ibsolution from source env download folder
    file_contents = read_file_content_from_ib(
        source_ib_host, source_api_token, copy_to_path, use_clients, **kwargs
    )

    # Upload file contents to target env upload folder
    resp = upload_chunks(
        target_ib_host, final_upload_path, target_api_token, file_contents
    )
    return resp, final_upload_path


def download_dependencies_from_dev_and_upload_to_prod(
    source_ib_host,
    target_ib_host,
    source_api_token,
    target_api_token,
    download_folder_path,
    upload_folder_path,
    dependency_dict,
    use_clients=False,
    **kwargs,
):
    """Downloads dependencies from dev and uploads to prod env.

    Downloads from dev marketplace to 'source_dependencies' and uploads to
    'target_dependencies' on prod.

    Args:
        source_ib_host: Source IB host URL.
        target_ib_host: Target IB host URL.
        source_api_token: Source IB API token.
        target_api_token: Target IB API token.
        download_folder_path: Path for download folder on source IB.
        upload_folder_path: Path for upload folder on target IB.
        dependency_dict: Dict of package names and versions.
        use_clients: Use clients if True.
        kwargs: Optional kwargs.
    Returns:
        List[str] - List of uploaded solution paths.
    """
    # TODO: Give possibility to use clients for one environment and the other

    # Create download/upload folders on dev/prod environments
    source_download_folder = os.path.join(download_folder_path, "source_dependencies")
    target_upload_folder = os.path.join(upload_folder_path, "target_dependencies")

    create_folder_if_it_does_not_exists(
        source_ib_host, source_api_token, source_download_folder
    )
    create_folder_if_it_does_not_exists(
        target_ib_host, target_api_token, target_upload_folder
    )

    # Copy all dependency packages from dev to prod
    upload_paths = []
    for package_name, package_version in dependency_dict.items():
        try:
            resp, uploaded_path = copy_marketplace_package_and_move_to_new_env(
                source_ib_host,
                target_ib_host,
                package_name,
                package_version,
                source_api_token,
                target_api_token,
                source_download_folder,
                target_upload_folder,
                use_clients=use_clients,
                **kwargs,
            )
        except Exception as e:
            print(
                "Error moving package name: {}, package_version: {}. Error: {}".format(
                    package_name, package_version, e
                )
            )
            continue

        # Keep track of uploaded paths
        upload_paths.append(uploaded_path)

    return upload_paths


def publish_dependencies(uploaded_ibsolutions, ib_host, api_token):
    """Publishes dependencies to marketplace.

    Args:
        uploaded_ibsolutions: List of ibsolution paths.
        ib_host: IB host URL.
        api_token: IB API token.
    Returns:
        None
    """
    for ib_solution_path in uploaded_ibsolutions:
        publish_resp = publish_to_marketplace(ib_host, api_token, ib_solution_path)
        print("Publish response for %s: %s", ib_solution_path, publish_resp)
