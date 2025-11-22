"""Tests for package management API endpoints."""

import pytest
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
def test_update_package_not_owner(test_client: TestClient, test_package):
    """Test updating a package when not the owner."""
    # Create a different user and get their auth headers
    # This would require additional setup in a real test
    update_data = {"summary": "Unauthorized update"}

    response = test_client.put(
        f"/api/v1/packages/{test_package.name}", json=update_data
    )

    # Should require authentication
    assert response.status_code == 401


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
        data = {
            "version": mock_version_data["version"],
            "summary": mock_version_data["summary"],
            "description": mock_version_data["description"],
            "python_version": mock_version_data["python_version"],
            "supported_revit_versions": mock_version_data["supported_revit_versions"],
            "author": mock_version_data["author"],
            "author_email": mock_version_data["author_email"],
            "license": mock_version_data["license"],
        }

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
            "version": test_package_version.version,  # Same version
            "summary": "Duplicate version",
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
