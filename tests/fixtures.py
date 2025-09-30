import pytest


@pytest.fixture
def mock_config():
    """Fixture providing mock configuration for testing.

    Returns:
        dict: Mock configuration containing source and target environment
            details including tokens, URLs, project IDs, orgs and workspaces.
    """
    return {
        "source": {
            "token": "source-token",
            "host_url": "https://source.example.com",
            "project_id": "source_project_id",
            "org": "source_org",
            "workspace": "source_workspace",
        },
        "target": {
            "token": "target-token",
            "host_url": "https://target.example.com",
            "org": "target_org",
            "workspace": "target_workspace",
        },
    }
