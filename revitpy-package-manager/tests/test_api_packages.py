"""Tests for package management API endpoints."""

import json

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient


@pytest.mark.unit
def test_list_packages_empty(test_client: TestClient):
    """Test listing packages when no packages exist."""
    response = test_client.get("/api/v1/packages/")

    assert response.status_code == 200
    data = response.json()

    assert data["packages"] == []
    assert data["total"] == 0
    assert data["page"] == 1
    assert data["per_page"] == 20
    assert not data["has_next"]
    assert not data["has_prev"]


@pytest.mark.integration
def test_list_packages_with_data(test_client: TestClient, test_package):
    """Test listing packages with existing data."""
    response = test_client.get("/api/v1/packages/")

    assert response.status_code == 200
    data = response.json()

    assert len(data["packages"]) == 1
    assert data["total"] == 1
    assert data["packages"][0]["name"] == test_package.name


@pytest.mark.unit
def test_get_package_not_found(test_client: TestClient):
    """Test getting a non-existent package."""
    response = test_client.get("/api/v1/packages/nonexistent-package")

    assert response.status_code == 404
    assert "Package not found" in response.json()["detail"]


@pytest.mark.integration
def test_get_package_success(test_client: TestClient, test_package):
    """Test getting an existing package."""
    response = test_client.get(f"/api/v1/packages/{test_package.name}")

    assert response.status_code == 200
    data = response.json()

    assert data["name"] == test_package.name
    assert data["summary"] == test_package.summary
    assert data["description"] == test_package.description


@pytest.mark.integration
def test_create_package_success(
    test_client: TestClient, auth_headers, mock_package_data
):
    """Test creating a new package."""
    response = test_client.post(
        "/api/v1/packages/", json=mock_package_data, headers=auth_headers
    )

    assert response.status_code == 201
    data = response.json()

    assert data["name"] == mock_package_data["name"]
    assert data["summary"] == mock_package_data["summary"]
    assert data["is_published"] is True


@pytest.mark.integration
def test_create_package_unauthorized(test_client: TestClient, mock_package_data):
    """Test creating a package without authentication."""
    response = test_client.post("/api/v1/packages/", json=mock_package_data)

    assert response.status_code == 401


@pytest.mark.integration
def test_create_package_duplicate_name(
    test_client: TestClient, auth_headers, test_package
):
    """Test creating a package with duplicate name."""
    package_data = {
        "name": test_package.name,
        "summary": "Duplicate package",
        "description": "This should fail",
    }

    response = test_client.post(
        "/api/v1/packages/", json=package_data, headers=auth_headers
    )

    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


@pytest.mark.integration
def test_update_package_success(test_client: TestClient, auth_headers, test_package):
    """Test updating an existing package."""
    update_data = {"summary": "Updated summary", "description": "Updated description"}

    response = test_client.put(
        f"/api/v1/packages/{test_package.name}", json=update_data, headers=auth_headers
    )

    assert response.status_code == 200
    data = response.json()

    assert data["summary"] == update_data["summary"]
    assert data["description"] == update_data["description"]


@pytest.mark.integration
def test_update_package_unauthenticated(test_client: TestClient, test_package):
    """Test updating a package without authentication."""
    update_data = {"summary": "Unauthorized update"}

    response = test_client.put(
        f"/api/v1/packages/{test_package.name}", json=update_data
    )

    assert response.status_code == 401


@pytest_asyncio.fixture
async def other_user_headers(test_client: TestClient, test_db_session):
    """Auth headers for a second user who owns nothing."""
    from revitpy_package_manager.registry.api.routers.auth import get_password_hash
    from revitpy_package_manager.registry.models.user import User

    other = User(
        username="otheruser",
        email="other@example.com",
        password_hash=get_password_hash("otherpassword"),
        is_active=True,
    )
    test_db_session.add(other)
    await test_db_session.commit()

    response = test_client.post(
        "/api/v1/auth/login",
        json={"username": "otheruser", "password": "otherpassword"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.mark.integration
def test_update_package_not_owner(
    test_client: TestClient, test_package, other_user_headers
):
    """A different authenticated user can't update someone else's package."""
    response = test_client.put(
        f"/api/v1/packages/{test_package.name}",
        json={"summary": "Hijacked"},
        headers=other_user_headers,
    )

    assert response.status_code == 404
    unchanged = test_client.get(f"/api/v1/packages/{test_package.name}")
    assert unchanged.json()["summary"] == test_package.summary


@pytest.mark.integration
def test_upload_version_not_owner(
    test_client: TestClient, test_package, test_package_file, other_user_headers
):
    """A different authenticated user can't upload versions of the package."""
    with open(test_package_file, "rb") as f:
        response = test_client.post(
            f"/api/v1/packages/{test_package.name}/versions",
            files={"file": (test_package_file.name, f, "application/gzip")},
            data={"metadata": json.dumps({"version": "9.9.9"})},
            headers=other_user_headers,
        )

    assert response.status_code == 404


@pytest.mark.integration
def test_delete_package_success(test_client: TestClient, auth_headers, test_package):
    """Test deleting a package (soft delete)."""
    response = test_client.delete(
        f"/api/v1/packages/{test_package.name}", headers=auth_headers
    )

    assert response.status_code == 204

    # Package should no longer be visible in public listing
    response = test_client.get(f"/api/v1/packages/{test_package.name}")
    assert response.status_code == 404


@pytest.mark.unit
def test_search_packages_empty_query(test_client: TestClient):
    """Test search with empty results."""
    response = test_client.get("/api/v1/packages/search?q=nonexistent")

    assert response.status_code == 200
    data = response.json()

    assert data["packages"] == []
    assert data["total"] == 0
    assert data["query"] == "nonexistent"


@pytest.mark.integration
def test_search_packages_with_results(test_client: TestClient, test_package):
    """Test search with matching results."""
    response = test_client.get(f"/api/v1/packages/search?q={test_package.name}")

    assert response.status_code == 200
    data = response.json()

    assert len(data["packages"]) >= 1
    assert any(pkg["name"] == test_package.name for pkg in data["packages"])


@pytest.mark.integration
def test_list_package_versions(
    test_client: TestClient, test_package, test_package_version
):
    """Test listing versions of a package."""
    response = test_client.get(f"/api/v1/packages/{test_package.name}/versions")

    assert response.status_code == 200
    data = response.json()

    assert len(data) == 1
    assert data[0]["version"] == test_package_version.version
    assert data[0]["package_id"] == str(test_package_version.package_id)


@pytest.mark.integration
def test_upload_package_version_success(
    test_client: TestClient,
    auth_headers,
    test_package,
    test_package_file,
    mock_version_data,
):
    """Test uploading a new package version."""
    with open(test_package_file, "rb") as f:
        files = {"file": (test_package_file.name, f, "application/gzip")}
        # Version metadata travels as one JSON form field (what the builder
        # CLI's publish sends), since lists/dependencies can't be flat fields.
        data = {"metadata": json.dumps(mock_version_data)}

        response = test_client.post(
            f"/api/v1/packages/{test_package.name}/versions",
            files=files,
            data=data,
            headers=auth_headers,
        )

    assert response.status_code == 201
    data = response.json()

    assert data["version"] == mock_version_data["version"]
    assert data["summary"] == mock_version_data["summary"]
    assert data["filename"] == test_package_file.name
    assert data["supported_revit_versions"] == ["2024", "2025"]
    assert data["file_size"] == test_package_file.stat().st_size
    assert [d["dependency_name"] for d in data["dependencies"]] == ["requests"]

    # The new version is listed afterwards
    listed = test_client.get(f"/api/v1/packages/{test_package.name}/versions")
    assert listed.status_code == 200
    assert [v["version"] for v in listed.json()] == [mock_version_data["version"]]


@pytest.mark.integration
def test_upload_duplicate_version(
    test_client: TestClient,
    auth_headers,
    test_package,
    test_package_version,
    test_package_file,
):
    """Test uploading a version that already exists."""
    with open(test_package_file, "rb") as f:
        files = {"file": (test_package_file.name, f, "application/gzip")}
        data = {
            "metadata": json.dumps(
                {
                    "version": test_package_version.version,  # Same version
                    "summary": "Duplicate version",
                }
            )
        }

        response = test_client.post(
            f"/api/v1/packages/{test_package.name}/versions",
            files=files,
            data=data,
            headers=auth_headers,
        )

    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]


@pytest.mark.integration
@pytest.mark.parametrize(
    "metadata",
    [
        "not json",
        json.dumps({"summary": "missing the required version"}),
        json.dumps({"version": "1.2.3", "supported_revit_versions": "2025"}),
    ],
)
def test_upload_invalid_metadata(
    test_client: TestClient, auth_headers, test_package, test_package_file, metadata
):
    """Malformed or invalid version metadata is a 422, not a 500."""
    with open(test_package_file, "rb") as f:
        response = test_client.post(
            f"/api/v1/packages/{test_package.name}/versions",
            files={"file": (test_package_file.name, f, "application/gzip")},
            data={"metadata": metadata},
            headers=auth_headers,
        )

    assert response.status_code == 422


@pytest.mark.integration
def test_get_package_stats(test_client: TestClient, test_package):
    """Test getting package download statistics."""
    response = test_client.get(f"/api/v1/packages/{test_package.name}/stats")

    assert response.status_code == 200
    data = response.json()

    assert "total_downloads" in data
    assert "downloads_last_day" in data
    assert "downloads_last_week" in data
    assert "downloads_last_month" in data
    assert "version_breakdown" in data
    assert "country_breakdown" in data


@pytest.mark.unit
def test_package_name_normalization():
    """Test package name normalization logic."""
    from revitpy_package_manager.registry.api.routers.packages import (
        normalize_package_name,
    )

    assert normalize_package_name("My_Package") == "my-package"
    assert normalize_package_name("Test Package") == "test-package"
    assert normalize_package_name("already-normalized") == "already-normalized"
    assert normalize_package_name("Mixed_Case-Package") == "mixed-case-package"


@pytest.mark.unit
def test_package_validation():
    """Test package data validation."""
    from pydantic import ValidationError
    from revitpy_package_manager.registry.api.schemas import PackageCreate

    # Valid package data
    valid_data = {
        "name": "test-package",
        "summary": "A test package",
        "description": "This is a test package",
    }

    package = PackageCreate(**valid_data)
    assert package.name == "test-package"

    # Invalid package data
    with pytest.raises(ValidationError):
        PackageCreate(name="")  # Empty name should fail


@pytest.mark.integration
def test_package_filtering_by_category(test_client: TestClient):
    """Test filtering packages by category."""
    response = test_client.get("/api/v1/packages/?category=utilities")

    assert response.status_code == 200
    data = response.json()

    # Should return empty list if no packages match category
    assert isinstance(data["packages"], list)


@pytest.mark.integration
def test_package_filtering_by_revit_version(test_client: TestClient):
    """Test filtering packages by Revit version."""
    response = test_client.get("/api/v1/packages/?revit_version=2025")

    assert response.status_code == 200
    data = response.json()

    # Should return empty list if no packages support the version
    assert isinstance(data["packages"], list)


@pytest.mark.integration
def test_package_filters_match_data(
    test_client: TestClient, auth_headers, mock_package_data, test_package_file
):
    """Category, keyword and Revit-version filters match stored list columns."""
    created = test_client.post(
        "/api/v1/packages/", json=mock_package_data, headers=auth_headers
    )
    assert created.status_code == 201
    name = mock_package_data["name"]

    for version, revit in (("1.0.0", ["2024", "2025"]), ("1.1.0", ["2025"])):
        with open(test_package_file, "rb") as f:
            uploaded = test_client.post(
                f"/api/v1/packages/{name}/versions",
                files={"file": (f"{name}-{version}.tar.gz", f, "application/gzip")},
                data={
                    "metadata": json.dumps(
                        {"version": version, "supported_revit_versions": revit}
                    )
                },
                headers=auth_headers,
            )
        assert uploaded.status_code == 201, uploaded.text

    def names(url: str) -> list[str]:
        response = test_client.get(url)
        assert response.status_code == 200
        return [p["name"] for p in response.json()["packages"]]

    assert names("/api/v1/packages/?category=utilities") == [name]
    assert names("/api/v1/packages/?category=geometry") == []
    # Two versions support 2025, but the package must be listed once
    assert names("/api/v1/packages/?revit_version=2025") == [name]
    assert names("/api/v1/packages/?revit_version=2024") == [name]
    assert names("/api/v1/packages/?revit_version=2019") == []
    # "mock" only occurs as a keyword/name substring; "revitpy" only as keyword
    assert names("/api/v1/packages/search?q=revitpy") == [name]
    assert names("/api/v1/packages/search?q=nomatch") == []


@pytest.mark.integration
def test_pagination_parameters(test_client: TestClient):
    """Test pagination parameters."""
    response = test_client.get("/api/v1/packages/?page=1&per_page=10")

    assert response.status_code == 200
    data = response.json()

    assert data["page"] == 1
    assert data["per_page"] == 10


@pytest.mark.integration
def test_search_pagination(test_client: TestClient):
    """Test search result pagination."""
    response = test_client.get("/api/v1/packages/search?q=test&page=1&per_page=5")

    assert response.status_code == 200
    data = response.json()

    assert data["page"] == 1
    assert data["per_page"] == 5
    assert data["query"] == "test"
