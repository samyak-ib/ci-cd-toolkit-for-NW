import os
from io import BytesIO
import requests
import json
from urllib.parse import quote
import time
import pathlib
import base64
import shutil
import zipfile
from importlib import resources


def __get_file_api_root(ib_host, api_version="v2", add_files_suffix=True):
    """
    Gets file api root from an ib host url

    Args:
        ib_host (str): IB host url (e.g. https://www.aihub.instabase.com)
        api_version (str): api_version to add to ib_host to create file api root url
        add_files_suffix (bool): flag indicating whether to add 'files' suffix to the api root

    Returns:
        str: IB host + file api root (e.g. https://www.aihub.instabase.com/api/v2/files)
    """
    if add_files_suffix:
        return os.path.join(*[ib_host, "api", api_version, "files"])
    return os.path.join(*[ib_host, "api", api_version])


def download_regression_suite(
    repo_owner="instabase",
    repo_name="aihub_regression_suite",
    branch="main",
    token="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",
    proxies=None,
):
    """
    Downloads the regression suite ZIP file, renames the folder inside, and repackages it into a new ZIP.

    Returns:
        str: Path to the newly zipped file.
    """
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/zipball/{branch}"
    headers = {"Authorization": f"token {token}", "Cache-Control": "no-cache"}

    response = requests.get(url, headers=headers, stream=True, proxies=proxies)
    response.raise_for_status()

    original_zip_path = "original_regression_suite.zip"
    renamed_zip_path = "regression_suite.zip"
    temp_extract_path = "temp_extracted"
    renamed_folder = "Regression Suite"

    with open(original_zip_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)

    with zipfile.ZipFile(original_zip_path, "r") as zip_ref:
        zip_ref.extractall(temp_extract_path)

    extracted_folder = next(
        os.path.join(temp_extract_path, d)
        for d in os.listdir(temp_extract_path)
        if os.path.isdir(os.path.join(temp_extract_path, d))
    )

    renamed_folder_path = os.path.join(temp_extract_path, renamed_folder)
    if os.path.exists(renamed_folder_path):
        shutil.rmtree(renamed_folder_path)
    os.rename(extracted_folder, renamed_folder_path)

    shutil.make_archive(renamed_folder, "zip", temp_extract_path, renamed_folder)

    os.remove(original_zip_path)
    shutil.rmtree(temp_extract_path)
    return renamed_zip_path


def upload_chunks(ib_host, path, api_token, file_data, proxies=None):
    """
    Uploads bytes to a location on the Instabase environment in chunks

    Args:
        ib_host (str): IB host url
        path (str): path on IB environment to upload to
        api_token (str): API token for IB environment
        file_data (bytes): Data to upload

    Returns:
        Response object
    """
    part_size = 10485760
    file_api_root = __get_file_api_root(ib_host)
    append_root_url = os.path.join(file_api_root, path)
    headers = {
        "Authorization": f"Bearer {api_token}",
    }

    bytes_io_content = BytesIO(file_data)
    with bytes_io_content as f:
        part_num = 0
        for chunk in iter(lambda: f.read(part_size), b""):
            headers["IB-Cursor"] = "0" if part_num == 0 else "-1"
            resp = requests.patch(
                append_root_url,
                headers=headers,
                data=chunk,
                verify=False,
                proxies=proxies,
            )
            part_num += 1

    if resp.status_code != 204:
        raise Exception(f"Upload failed: {resp.content}")
    return resp


def upload_file(ib_host, api_token, file_path, file_data, proxies=None):
    """
    Upload single file to path on IB environment

    Args:
        ib_host (str): IB host url
        api_token (str): API token for IB environment
        file_path (str): path on IB environment to upload to
        file_data (bytes): Data to upload

    Returns:
        Response object
    """
    file_api_root = __get_file_api_root(ib_host)
    url = os.path.join(file_api_root, file_path)
    headers = {"Authorization": f"Bearer {api_token}"}

    resp = requests.put(
        url, headers=headers, data=file_data, verify=False, proxies=proxies
    )

    if resp.status_code != 204:
        raise Exception(f"Upload file failed: {resp.content}")

    return resp


def read_file_through_api(ib_host, api_token, path_to_file, proxies=None):
    """
    Read file from IB environment

    Args:
        ib_host (str): IB host url
        api_token (str): API token for IB environment
        path_to_file (str): path to file on IB environment

    Returns:
        Response object
    """
    file_api_root = __get_file_api_root(ib_host)
    url = os.path.join(*[file_api_root, path_to_file])

    params = {"expect-node-type": "file"}
    headers = {"Authorization": f"Bearer {api_token}"}

    resp = requests.get(
        url, headers=headers, params=params, verify=False, proxies=proxies
    )

    if resp.status_code != 200:
        raise Exception(f"Error reading file: {resp.content}, for url: {url}")

    return resp


def publish_to_marketplace(ib_host, api_token, ibsolution_path, proxies=None):
    """
    Publishes an ibsolution to Marketplace

    Args:
        ib_host (str): IB host url
        api_token (str): API token for IB environment
        ibsolution_path (str): path to .ibsolution file

    Returns:
        Response object
    """
    file_api_v1 = __get_file_api_root(ib_host, api_version="v1", add_files_suffix=False)
    headers = {"Authorization": f"Bearer {api_token}"}
    url = f"{file_api_v1}/marketplace/publish"

    args = {"ibsolution_path": ibsolution_path}
    json_data = json.dumps(args)

    resp = requests.post(
        url, headers=headers, data=json_data, verify=False, proxies=proxies
    )
    try:
        resp_json = resp.json()
        print(f"File: {url}, Solution publish status: {resp_json}")
    except json.JSONDecodeError:
        print(
            f"Error publishing ibsolution_path: {ibsolution_path}. "
            f"Solution publish status exception: {resp.content}"
        )
        raise

    return resp


def make_api_request(
    url, api_token, method="get", payload=None, context=None, verify=True, proxies=None
):
    """
    Makes an API request with common error handling and logging.  Raises an exception on failure.

    Args:
        url (str): Request URL
        api_token (str): API token
        method (str): HTTP method (get/post)
        payload (dict): Request payload for POST
        context (str): Context header value
        verify (bool): Verify SSL

    Returns:
        dict: Response JSON on success

    Raises:
        requests.exceptions.RequestException: If the API request fails.
    """
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json",
    }
    if context:
        headers["Ib-Context"] = context

    try:
        if method == "get":
            response = requests.get(
                url, headers=headers, verify=verify, proxies=proxies
            )
        elif method == "patch":
            response = requests.patch(
                url,
                headers=headers,
                data=json.dumps(payload),
                verify=verify,
                proxies=proxies,
            )
        else:
            response = requests.post(
                url,
                headers=headers,
                data=json.dumps(payload),
                verify=verify,
                proxies=proxies,
            )

        response.raise_for_status()
        print(f"Request was successful. Response content: {response.content}")
        return response.json()
    except requests.exceptions.RequestException as err:
        print(f"API request failed: {err}")
        raise


def publish_advanced_app(target_url, api_token, payload, context, proxies=None):
    """Publish an advanced app"""
    url = f"{target_url}/api/v2/zero-shot-idp/projects/advanced-app"
    return make_api_request(url, api_token, "post", payload, context, proxies=proxies)


def publish_build_app(target_url, api_token, payload, context, proxies=None):
    """Publish a build app"""
    url = f"{target_url}/api/v2/aihub/build/projects/app"
    return make_api_request(url, api_token, "post", payload, context, proxies=proxies)


def add_the_state(target_url, api_token, payload, context, app_id, proxies=None):
    """Add the state to the app and update sharing settings"""
    url = f"{target_url}/api/v2/solutions/deployed/{app_id}"
    response = make_api_request(
        url, api_token, "patch", payload, context, proxies=proxies
    )

    if payload["state"] == "PRODUCTION":
        sharing_url = f"{target_url}/api/v2/solutions/deployed/{app_id}/sharing/orgs"
        payload = {"orgs": [context]}
        make_api_request(
            sharing_url, api_token, "patch", payload, context, proxies=proxies
        )

    return response


def create_deployment(
    target_url, api_token, payload, context, deployment_id=None, proxies=None
):
    """Create deployment in target"""
    if deployment_id:
        url = f"{target_url}/api/v2/aihub/deployments/{deployment_id}/deployed-solution-id"
        payload = {"deployed_solution_id": payload["deployed_solution_id"]}
        return make_api_request(
            url, api_token, "patch", payload, context, proxies=proxies
        )
    else:
        url = f"{target_url}/api/v2/aihub/deployments/"
        return make_api_request(
            url, api_token, "post", payload, context, proxies=proxies
        )


def check_job_status(ib_host, job_id, job_type, api_token, proxies=None):
    """
    Check status of a job using Job Status API

    Args:
        ib_host (str): IB host url
        job_id (str): Job ID to check
        job_type (str): Job type [flow, refiner, job, async, group]
        api_token (str): API token

    Returns:
        Response object
    """
    url = f"{ib_host}/api/v1/jobs/status?job_id={job_id}&type={job_type}"
    headers = {"Authorization": f"Bearer {api_token}"}

    resp = requests.get(url, headers=headers, verify=False, proxies=proxies)
    content = json.loads(resp.content)

    if resp.status_code != 200 or (
        "status" in content and content["status"] == "ERROR"
    ):
        raise Exception(f"Error checking job status: {resp.content}")

    return resp


def check_job_status_build(target_url, api_token, job_id, proxies=None):
    """
    Continuously checks build job status until DONE

    Args:
        target_url (str): Target URL
        api_token (str): API token
        job_id (str): Job ID

    Returns:
        str: Deployed solution ID on success
        None: On failure
    """
    url = f"{target_url}/api/v1/jobs/status?job_id={job_id}&type=async"
    headers = {"Authorization": f"Bearer {api_token}"}

    for _ in range(15):
        try:
            response = requests.get(url, headers=headers, verify=True, proxies=proxies)
            response.raise_for_status()
            job_data = response.json()
            state = job_data.get("state", "UNKNOWN")

            print(f"Job ID: {job_id}, State: {state}")
            if state == "DONE":
                print("Job completed successfully.")
                if (
                    "results" in job_data
                    and isinstance(job_data["results"], list)
                    and len(job_data["results"]) > 0
                ):
                    deployed_id = job_data["results"][0].get("deployed_solution_id")
                    if deployed_id:
                        return deployed_id
                print(f"error: {job_data.get('results')}")
                raise Exception("Error in job results")
            time.sleep(5)
        except requests.exceptions.RequestException as e:
            print(f"Error while checking job status: {e}")
            raise
    raise Exception("Job failed to complete")


def unzip_files(ib_host, api_token, zip_path, destination_path=None, proxies=None):
    """
    Unzip file on IB environment

    Args:
        ib_host (str): IB host url
        api_token (str): API token
        zip_path (str): Path to zip file
        destination_path (str): Path to unzip to

    Returns:
        Response object
    """
    url = os.path.join(*[ib_host, "api/v2", "files", "extract"])
    destination_path = destination_path or ".".join(zip_path.split(".")[:-1])

    headers = {"Authorization": f"Bearer {api_token}"}
    data = json.dumps({"src_path": zip_path, "dst_path": destination_path})

    resp = requests.post(url, headers=headers, data=data, verify=False, proxies=proxies)

    if resp.status_code != 202:
        raise Exception(f"Unable to unzip files: {resp.content}")

    return resp


def compile_solution(
    ib_host,
    api_token,
    solution_path,
    relative_flow_path=None,
    solution_builder=False,
    solution_version=None,
    proxies=None,
):
    """
    Compiles a flow

    :param ib_host: (string) IB host url (e.g. https://www.aihub.instabase.com)
    :param api_token: (string) api token for IB environment
    :param solution_path: (string) path to root folder of solution
                              (e.g. vinay.thapa/testing/fs/Instabase Drive/testing_solution)
    :param relative_flow_path: relative path of flow from solution_path (e.g. testing_flow.ibflow)
                               full flow path is {solutionPath}/{relative_flow_path} (used for filesystem projects only)
    :param solution_builder: (bool) if the solution to be compiled is a solution builder project
    :param solution_version: (string) version of compiled solution (used for solution builder projects only)
    :return: Response object
    """
    # TODO: API docs issue
    path_encoded = quote(solution_path)

    url = os.path.join(*[ib_host, "api/v1", "flow_binary", "compile", path_encoded])

    if solution_builder:
        p = pathlib.Path(solution_path)
        bin_path = os.path.join(
            *p.parts[:-1], "builds", f"{solution_version}.ibflowbin"
        )
        flow_project_root = os.path.join(*p.parts[:7])
        flow_path = os.path.join(*p.parts[7:])
    else:
        bin_path = relative_flow_path.replace(".ibflow", ".ibflowbin")
        bin_path = os.path.join(solution_path, bin_path)
        flow_project_root = os.path.join(
            solution_path, *relative_flow_path.split("/")[:-1]
        )
        flow_path = relative_flow_path.split("/")[-1]

    headers = {"Authorization": "Bearer {0}".format(api_token)}
    data = json.dumps(
        {
            "binary_type": "Single Flow",
            "flow_project_root": flow_project_root,
            "predefined_binary_path": bin_path,
            "settings": {
                "flow_file": flow_path,
                "is_flow_v3": True,
            },
        }
    )
    resp = requests.post(
        url.replace("//d", "/d"),
        headers=headers,
        data=data,
        verify=False,
        proxies=proxies,
    )

    # Verify request is successful
    content = json.loads(resp.content)
    if resp.status_code != 200 or (
        "status" in content and content["status"] == "ERROR"
    ):
        raise Exception(f"Error with compile solution job: {resp.content}")

    return resp


def copy_file_within_ib(
    ib_host,
    api_token,
    source_path,
    destination_path,
    use_clients=False,
    proxies=None,
    **kwargs,
):
    """
    Copies a file within an IB environment

    Args:
        ib_host (str): IB host url
        api_token (str): API token
        source_path (str): Source path
        destination_path (str): Destination path
        use_clients (bool): Use clients if in flow

    Returns:
        Response object if use_clients is False
    """
    if use_clients:
        clients, err = kwargs["_FN_CONTEXT_KEY"].get_by_col_name("CLIENTS")
        _, err = clients.ibfile.copy(
            source_path, destination_path
        )  # Renamed copy to copy_op
        if err:
            print(f"Error copying file: {err}")
            raise Exception(f"Error copying file: {err}")
    else:
        file_api_root = __get_file_api_root(ib_host)
        url = os.path.join(file_api_root, "copy")
        headers = {"Authorization": f"Bearer {api_token}"}
        data = json.dumps({"src_path": source_path, "dst_path": destination_path})

        resp = requests.post(
            url, headers=headers, data=data, verify=False, proxies=proxies
        )

        if resp.status_code != 202:
            raise Exception(f"Error copying file: {resp.content}")

        return resp


def read_file_content_from_ib(
    ib_host, api_token, file_path_to_read, use_clients=False, proxies=None, **kwargs
):
    """
    Reads content of a file on IB environment

    Args:
        ib_host (str): IB host url
        api_token (str): API token
        file_path_to_read (str): Path to read
        use_clients (bool): Use clients if in flow

    Returns:
        bytes: File content
    """
    if not use_clients:
        resp = read_file_through_api(
            ib_host, api_token, file_path_to_read, proxies=proxies
        )
        return resp.content
    else:
        clients, err = kwargs["_FN_CONTEXT_KEY"].get_by_col_name("CLIENTS")
        if clients.ibfile.is_file(file_path_to_read):
            file_content, err = clients.ibfile.read_file(file_path_to_read)
            if err:
                print(f"is file read err: {err}")
                raise Exception(f"Error reading file: {err}")
            return file_content
        else:
            print(f"Not valid file: {file_path_to_read}")
            raise Exception(f"Not valid file: {file_path_to_read}")


def get_file_metadata(ib_host, api_token, file_path, proxies=None):
    """
    Get metadata of file using file API

    Args:
        ib_host (str): IB host url
        api_token (str): API token
        file_path (str): Path to file

    Returns:
        Response object
    """
    file_api_root = __get_file_api_root(ib_host)
    url = os.path.join(file_api_root, file_path)

    headers = {
        "Authorization": f"Bearer {api_token}",
        "IB-Retry-Config": json.dumps({"retries": 2, "backoff-seconds": 1}),
    }

    return requests.head(url, headers=headers, proxies=proxies)


def create_folder_if_it_does_not_exists(ib_host, api_token, folder_path, proxies=None):
    """
    Creates folder in IB environment if it doesn't exist

    Args:
        ib_host (str): IB host url
        api_token (str): API token
        folder_path (str): Path to create

    Returns:
        Response object
    """
    file_api_root = __get_file_api_root(ib_host)
    metadata_url = os.path.join(file_api_root, folder_path)
    headers = {"Authorization": f"Bearer {api_token}"}

    r = requests.head(metadata_url, headers=headers, verify=False, proxies=proxies)
    if r.status_code == 404:
        create_url = os.path.dirname(metadata_url)
        folder_name = os.path.basename(folder_path)
        data = json.dumps({"name": folder_name, "node_type": "folder"})
        return requests.post(
            create_url, headers=headers, data=data, verify=False, proxies=proxies
        )


def list_directory(ib_host, folder, api_token, proxies=None):
    """
    Lists directory on IB filesystem and returns full paths

    Args:
        ib_host (str): IB host url
        folder (str): Folder to list
        api_token (str): API token

    Returns:
        list: List of paths in directory
    """
    file_api_root = __get_file_api_root(ib_host)
    url = os.path.join(file_api_root, folder)
    headers = {"Authorization": f"Bearer {api_token}"}

    paths = []
    has_more = None
    start_token = None

    while has_more is not False:
        params = {"expect-node-type": "folder", "start-token": start_token}
        resp = requests.get(url, headers=headers, params=params, proxies=proxies)

        content = json.loads(resp.content)
        if resp.status_code != 200 or (
            "status" in content and content["status"] == "ERROR"
        ):
            raise Exception(f"Error checking job status: {resp.content}")

        paths.extend([node["full_path"] for node in content["nodes"]])
        has_more = content["has_more"]
        start_token = content["next_page_token"]

    return paths


def wait_until_job_finishes(ib_host, job_id, job_type, api_token, proxies=None):
    """
    Wait until job finishes using job status API

    Args:
        ib_host (str): IB host url
        job_id (str): Job ID
        job_type (str): Job type
        api_token (str): API token

    Returns:
        bool: True if completed successfully
    """
    while True:
        job_status_response = check_job_status(
            ib_host, job_id, job_type, api_token, proxies=proxies
        )
        content = json.loads(job_status_response.content)

        if content["status"] != "OK":
            raise Exception(f"Job failed: {content}")

        state = content["state"]
        if state in ["DONE", "COMPLETE"]:
            results_status = all(
                result["status"] == "OK" for result in content.get("results", [])
            )
            if not results_status:
                raise Exception(f"Job completed with errors: {content}")
            return content
        time.sleep(5)


def delete_folder_or_file_from_ib(
    path_to_delete,
    ib_host=None,
    api_token=None,
    use_clients=False,
    proxies=None,
    **kwargs,
):
    """
    Delete folder/file from Instabase

    Args:
        path_to_delete (str): Path to delete
        ib_host (str): IB host url
        api_token (str): API token
        use_clients (bool): Use clients if in flow
    """
    if use_clients:
        clients, err = kwargs["_FN_CONTEXT_KEY"].get_by_col_name("CLIENTS")
        _, err = clients.ibfile.rm(
            path_to_delete
        )  # Discard rm result, only care about error
        if err:
            print(f"Error deleting file: {err}")
            raise Exception(f"Error deleting file: {err}")
    else:
        file_api_root = __get_file_api_root(ib_host)
        url = os.path.join(file_api_root, path_to_delete)
        headers = {"Authorization": f"Bearer {api_token}"}
        requests.delete(url, headers=headers, verify=False, proxies=proxies)


def get_app_details(target_url, api_token, context, app_id, proxies=None):
    """Get details of deployed app"""
    url = f"{target_url}/api/v2/solutions/deployed/{app_id}"
    return make_api_request(url, api_token, "get", context=context, proxies=proxies)


def get_deployment_details(target_url, api_token, context, deployment_id, proxies=None):
    """Get details of deployment"""
    url = f"{target_url}/api/v2/aihub/deployments/{deployment_id}"
    return make_api_request(url, api_token, "get", context=context, proxies=proxies)


def read_image(image_name="icon.png"):
    """
    Read image file from package resources

    Args:
        image_name (str): Image filename

    Returns:
        bytes: Image binary content
    """
    try:
        with resources.files("ib_cicd.assets").joinpath(image_name).open("rb") as f:
            return f.read()
    except FileNotFoundError:
        print(f"Image file '{image_name}' not found in the package.")
        raise


def generate_flow(
    ib_host,
    api_token,
    project_id,
    context,
    icon_path=None,
    proxies=None,
):
    """
    Generate flow from build project and create snapshot

    Args:
        ib_host (str): IB host url
        api_token (str): API token
        project_id (str): Project ID
        icon_path (str): Path to the icon file
        context (str): organization

    Returns:
        dict: API response on success
        None: On failure
    """
    url = f"{ib_host}/api/v2/aihub/build/projects/{project_id}/generate-flow"

    icon_base64 = None
    if icon_path:
        with open(icon_path, "rb") as icon_file:
            icon_bytes = icon_file.read()
        icon_base64 = base64.b64encode(icon_bytes).decode("utf-8")
    else:
        icon_bytes = read_image()
        icon_base64 = base64.b64encode(icon_bytes).decode("utf-8")

    payload = {
        "icon": icon_base64,
        "should_create_snapshot": True,
        "use_refinement_lines": True,
        "custom_request_args": {
            "enable_map_reduce_extraction": True,
            "reasoning_confidence": True,
        },
    }

    headers = {
        "Authorization": f"Bearer {api_token}",
        "Referer": f"{ib_host}/build/{project_id}/app/create",
        "Content-Type": "application/json",
        "ib-context": context,
    }

    try:
        response = requests.post(
            url, headers=headers, data=json.dumps(payload), proxies=proxies
        )
        response.raise_for_status()
        print(f"Request was successful. Response content: {response.content}")
        return response.json()
    except requests.exceptions.RequestException as err:
        print(f"API request failed: {err}")
        raise


def delete_app(host, token, app_id, org, proxies=None):
    """
    Delete an app from the target environment.

    Args:
        host: The target host URL
        token: API token for authentication
        app_id: The ID of the app to delete
        org: The organization under which the app exists

    Returns:
        Response object on success, None on failure
    """
    url = f"{host}/api/v2/aihub/build/projects/app?app_id={app_id}"

    headers = {"Authorization": f"Bearer {token}"}

    try:
        response = requests.delete(url, headers=headers, proxies=proxies)
        response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
        return response
    except requests.exceptions.RequestException as e:
        print(f"Error deleting app: {e}")
        raise


def delete_build_project(host, token, project_id, proxies=None):
    """
    Delete a build project from the target environment.

    Args:
        host (str): The target host URL
        token (str): API token for authentication
        project_id (str): The ID of the project to delete

    Returns:
        Response object on success, None on failure
    """
    url = f"{host}/api/v2/aihub/build/projects?project_id={project_id}"
    headers = {"Authorization": f"Bearer {token}"}

    try:
        response = requests.delete(url, headers=headers, proxies=proxies)
        response.raise_for_status()
        return response
    except requests.exceptions.RequestException as e:
        print(f"Error deleting build project: {e}")
        raise


def get_published_app_id(ib_host, api_token, project_id, proxies=None):
    """
    Get the app_id of the published build app.

    Args:
        ib_host (str): IB host URL
        api_token (str): API token for authentication
        project_id (str): Project ID

    Returns:
        str: The app_id of the published build app
    """
    url = (
        f"{ib_host}/api/v2/aihub/build/projects?proj_id={project_id}&query_option=uuid"
    )
    headers = {"Authorization": f"Bearer {api_token}"}

    try:
        response = requests.get(url, headers=headers, verify=False, proxies=proxies)
        response.raise_for_status()

        data = response.json()
        if "projects" in data and len(data["projects"]) > 0:
            app_id = data["projects"][0].get("active_deployed_solution_id")
            if app_id:
                print(f"Successfully retrieved app_id: {app_id}")
                return app_id
            else:
                print("active_deployed_solution_id not found in project data")
                raise Exception("active_deployed_solution_id not found in project data")
        else:
            print("No projects found in response")
            raise Exception("No projects found in response")

    except requests.exceptions.RequestException as e:
        print(f"Error retrieving app_id: {e}")
        raise


def trigger_regression_run(
    url,
    api_token,
    flow_path,
    config,
    input_files_path,
    tags=[],
    pipeline_ids=[],
    proxies=None,
):
    """
    Trigger the regression run flow for a given project.

    Args:
        url (str): URL of the IB environment
        api_token (str): API token for authentication
        flow_path (str): Path to the flow
        config (dict): Configuration for the flow
        input_files_path (str): Path to the input files
        tags (list): List of tags
        pipeline_ids (list): List of pipeline IDs

    Returns:
        str: Job ID on success, empty string on failure
    """
    url = f"{url}/api/v1/flow/run_flow_async"
    headers = {"Authorization": f"Bearer {api_token}"}
    payload = {
        "ibflow_path": flow_path,
        "input_dir": input_files_path,
        "compile_and_run_as_binary": True,
        "output_has_run_id": True,
        "delete_out_dir": False,
        "log_to_timeline": True,
        "disable_step_timeout": False,
        "step_timeout": 4500,
        "enable_ibdoc": True,
        "compare_against_golden_set": False,
        "tags": tags,
        "pipeline_ids": pipeline_ids,
        "webhook_config": {"headers": {}},
        "runtime_config": config,
    }

    try:
        response = requests.post(
            url, headers=headers, data=json.dumps(payload), proxies=proxies
        )
        response.raise_for_status()
        response_data = response.json()

        if response_data["status"] == "OK":
            print("Triggered regression test runner flow successfully")
            return response_data["data"]["job_id"]

        if response_data["status"] == "ERROR":
            if "msg" in response_data:
                print(
                    "Post flow failure: Unable to trigger the regression test runner flow, msg: "
                    + response_data["msg"]
                )
            else:
                print(
                    "Post flow failure: Unable to trigger the regression test runner flow"
                )
            raise Exception("Error triggering regression run")

        raise Exception("Unexpected response status")
    except requests.exceptions.RequestException as e:
        print(f"Error triggering regression run: {e}")
        raise
