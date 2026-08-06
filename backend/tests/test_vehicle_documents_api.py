"""Araç detayı "Dosyalar ve Ekler" API'si — yükleme/listeleme/silme, şirket
kapsamına (multi-tenant) göre izole edildiğini de doğrular."""

from __future__ import annotations

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status
from rest_framework.test import APIClient

from backend.apps.companies.models import Company, CustomUser, UserRole
from backend.apps.vehicles.models import Vehicle, VehicleDocument

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _tmp_media_root(settings, tmp_path):
    """Testler gerçek dosya yazar (FileField) — repo'nun media/ klasörünü
    kirletmemek için her test kendi geçici dizinine yazar."""
    settings.MEDIA_ROOT = tmp_path


@pytest.fixture
def other_company() -> Company:
    return Company.objects.create(name="other-doc-tenant", tax_number="7770007777")


@pytest.fixture
def other_manager(other_company: Company) -> CustomUser:
    return CustomUser.objects.create_user(
        username="other_doc_manager",
        password="test-pass-123",
        company=other_company,
        role=UserRole.FLEET_MANAGER,
    )


@pytest.fixture
def other_client(other_manager: CustomUser) -> APIClient:
    api_client = APIClient()
    api_client.force_authenticate(user=other_manager)
    return api_client


@pytest.fixture
def vehicle(company: Company) -> Vehicle:
    return Vehicle.objects.create(
        company=company, plate_number="34DOC001", brand="Renault", model="Clio", production_year=2024
    )


def test_upload_document_creates_real_record_with_server_derived_metadata(
    client: APIClient, vehicle: Vehicle, manager: CustomUser
) -> None:
    upload = SimpleUploadedFile("ruhsat.pdf", b"%PDF-1.4 fake content", content_type="application/pdf")

    response = client.post(
        f"/api/vehicles/{vehicle.pk}/documents/",
        {"file": upload, "label": "Ruhsat fotokopisi"},
        format="multipart",
    )

    assert response.status_code == status.HTTP_201_CREATED, response.data
    doc = VehicleDocument.objects.get(vehicle=vehicle)
    assert doc.original_filename == "ruhsat.pdf"
    assert doc.content_type == "application/pdf"
    assert doc.size > 0
    assert doc.uploaded_by == manager
    assert response.data["label"] == "Ruhsat fotokopisi"


def test_upload_document_rejects_disallowed_extension(client: APIClient, vehicle: Vehicle) -> None:
    upload = SimpleUploadedFile("virus.exe", b"MZ fake exe content", content_type="application/octet-stream")

    response = client.post(
        f"/api/vehicles/{vehicle.pk}/documents/",
        {"file": upload},
        format="multipart",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert not VehicleDocument.objects.filter(vehicle=vehicle).exists()


def test_upload_document_rejects_oversized_file(client: APIClient, vehicle: Vehicle) -> None:
    from backend.apps.vehicles.serializers import MAX_DOCUMENT_SIZE_BYTES

    oversized = SimpleUploadedFile(
        "buyuk.pdf", b"0" * (MAX_DOCUMENT_SIZE_BYTES + 1), content_type="application/pdf"
    )

    response = client.post(
        f"/api/vehicles/{vehicle.pk}/documents/",
        {"file": oversized},
        format="multipart",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert not VehicleDocument.objects.filter(vehicle=vehicle).exists()


def test_list_documents_scoped_to_own_company(
    client: APIClient, other_client: APIClient, vehicle: Vehicle
) -> None:
    VehicleDocument.objects.create(
        vehicle=vehicle,
        file=SimpleUploadedFile("a.pdf", b"data"),
        original_filename="a.pdf",
        size=4,
    )

    response = client.get(f"/api/vehicles/{vehicle.pk}/documents/")
    assert response.status_code == status.HTTP_200_OK
    assert response.data["count"] == 1

    other_response = other_client.get(f"/api/vehicles/{vehicle.pk}/documents/")
    assert other_response.status_code == status.HTTP_404_NOT_FOUND


def test_delete_document_removes_record(client: APIClient, vehicle: Vehicle) -> None:
    doc = VehicleDocument.objects.create(
        vehicle=vehicle,
        file=SimpleUploadedFile("b.pdf", b"data"),
        original_filename="b.pdf",
        size=4,
    )

    response = client.delete(f"/api/vehicle-documents/{doc.pk}/")

    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert not VehicleDocument.objects.filter(pk=doc.pk).exists()


def test_delete_document_from_other_company_is_not_found(
    other_client: APIClient, vehicle: Vehicle
) -> None:
    doc = VehicleDocument.objects.create(
        vehicle=vehicle,
        file=SimpleUploadedFile("c.pdf", b"data"),
        original_filename="c.pdf",
        size=4,
    )

    response = other_client.delete(f"/api/vehicle-documents/{doc.pk}/")

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert VehicleDocument.objects.filter(pk=doc.pk).exists()
