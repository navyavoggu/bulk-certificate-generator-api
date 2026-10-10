from pathlib import Path
from fastapi.testclient import TestClient
from app.main import create_app

def test_create_job_and_progress(client, payload):
    response = client.post("/jobs", json=payload)
    assert response.status_code == 202
    data = response.json()
    assert data["total_count"] == 2
    assert data["status"] == "queued"
    job_id = data["id"]

    # Starlette TestClient executes BackgroundTasks before returning from the request.
    status_response = client.get(f"/jobs/{job_id}")
    assert status_response.status_code == 200
    job = status_response.json()
    assert job["status"] == "completed"
    assert job["processed_count"] == 2
    assert job["success_count"] == 2
    assert job["failed_count"] == 0
    assert job["progress_percent"] == 100.0

def test_input_validation(client, payload):
    bad_payload = {**payload, "recipients": [{"name": "   ", "email": "not-an-email"}]}
    response = client.post("/jobs", json=bad_payload)
    assert response.status_code == 422

    empty_recipients = {**payload, "recipients": []}
    response = client.post("/jobs", json=empty_recipients)
    assert response.status_code == 422

def test_certificate_generation_and_download(client, payload):
    job_response = client.post("/jobs", json=payload)
    job = job_response.json()
    cert = next(c for c in job["certificates"] if c["recipient_name"] == "Asha Rao")
    download = client.get(f"/certificates/{cert['id']}")
    assert download.status_code == 200
    assert download.headers["content-type"] == "application/pdf"
    assert download.content.startswith(b"%PDF")

def test_list_certificates(client, payload):
    job = client.post("/jobs", json=payload).json()
    response = client.get(f"/jobs/{job['id']}/certificates")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert all(c["status"] == "succeeded" for c in data["certificates"])

def test_missing_job_and_certificate_return_404(client):
    assert client.get("/jobs/not-a-real-job").status_code == 404
    assert client.get("/certificates/not-a-real-certificate").status_code == 404

def test_one_certificate_failure_does_not_stop_others(tmp_path, payload):
    def selective_generator(output_path, recipient_name, event_name, issuer_name, certificate_date):
        if recipient_name == "Asha Rao":
            raise RuntimeError("Simulated PDF generation failure")
        from app.certificate_generator import generate_certificate
        return generate_certificate(output_path, recipient_name, event_name, issuer_name, certificate_date)

    app = create_app(f"sqlite:///{(tmp_path / 'failure.db').as_posix()}", tmp_path / "failure_certs", selective_generator)
    with TestClient(app) as test_client:
        job = test_client.post("/jobs", json=payload).json()
        result = test_client.get(f"/jobs/{job['id']}").json()
        assert result["status"] == "completed_with_errors"
        assert result["processed_count"] == 2
        assert result["success_count"] == 1
        assert result["failed_count"] == 1
        by_name = {c["recipient_name"]: c for c in result["certificates"]}
        assert by_name["Asha Rao"]["status"] == "failed"
        assert "Simulated PDF generation failure" in by_name["Asha Rao"]["error_message"]
        assert by_name["Ravi Kumar"]["status"] == "succeeded"
