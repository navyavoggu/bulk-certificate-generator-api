# Bulk Certificate Generator API

A Python REST API that accepts one bulk request, validates recipients, generates personalized PDF certificates from one predefined template, tracks per-certificate and job status, and serves generated files.

## Technology

- Python 3.10+
- FastAPI
- SQLAlchemy 2.x and SQLite
- ReportLab for PDF certificates
- Pytest and FastAPI TestClient

## Features

- Bulk job creation (1–500 recipients per request)
- Request validation for names, email addresses, event and issuer names
- Background job processing using FastAPI `BackgroundTasks`
- Independent per-recipient failure handling
- Job progress counters and status (`queued`, `running`, `completed`, `completed_with_errors`, `failed`)
- Per-certificate status (`pending`, `processing`, `succeeded`, `failed`)
- Downloadable PDF certificates
- OpenAPI/Swagger UI at `/docs`
- Tests for job creation, validation, generation, progress, failure isolation, listing and downloads

## Setup on Windows (VS Code)

Open the project folder in VS Code. In the integrated terminal (PowerShell), run:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If PowerShell blocks activation, run this once in that terminal, then activate again:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

## Run the API

```powershell
uvicorn app.main:app --reload
```

Visit:
- Swagger UI: http://127.0.0.1:8000/docs
- Health check: http://127.0.0.1:8000/health

SQLite database is created automatically as `certificate_generator.db`. PDFs are written to `storage/certificates/`.

## Create a bulk generation job

In Swagger UI, expand `POST /jobs` and use this JSON:

```json
{
  "event_name": "Python Fundamentals Workshop",
  "issuer_name": "Example Training Institute",
  "certificate_date": "2026-10-09",
  "recipients": [
    {"name": "Asha Rao", "email": "asha@example.com"},
    {"name": "Ravi Kumar", "email": "ravi@example.com"},
    {"name": "Meera Shah", "email": "meera@example.com"}
  ]
}
```

The API returns HTTP `202 Accepted`, a unique `id`, job counters, and initial certificate records. FastAPI background tasks begin processing after the response is sent. For a local development server, the worker runs inside the API process.

## Check job status and progress

```http
GET /jobs/{job_id}
```

The response includes:
- `status`
- `total_count`, `processed_count`, `success_count`, `failed_count`
- `progress_percent`
- per-recipient status and error details

## List certificates for a job

```http
GET /jobs/{job_id}/certificates
```

## Download a certificate

```http
GET /certificates/{certificate_id}
```

This returns a PDF attachment when generation succeeded. A certificate that is still processing returns HTTP `409`; a failed certificate also returns `409` with a helpful message. Unknown IDs return `404`.

## Run tests

```powershell
python -m pytest -v
```

The tests use temporary SQLite databases and temporary certificate directories; they do not modify your development database or output folder.

## Design decisions

1. **FastAPI:** provides typed request validation, automatic API documentation, and easy test-client support.
2. **SQLite + SQLAlchemy:** a lightweight relational database appropriate for a self-contained assignment. Tables store jobs and individual certificate records.
3. **One predefined template:** ReportLab creates landscape A4 PDF certificates; no template editor or multiple designs are included.
4. **Bulk processing:** one request creates one job and one record per recipient. FastAPI `BackgroundTasks` processes recipients after the response. This avoids holding the request open while generating the entire batch. For high-volume production systems, replace this with a durable queue (e.g. Celery/RQ) and separate workers; in-process background tasks are not a durable job queue.
5. **Failure isolation:** each certificate is generated in its own `try/except` block. Failures are stored on that certificate and do not prevent subsequent recipients from being processed.
6. **Progress tracking:** counters are updated after each recipient. Mixed results finish as `completed_with_errors`; all failures finish as `failed`; no failures finish as `completed`.
7. **Input validation:** Pydantic validates request structure, names, optional emails, and the 1–500 recipient limit before creating a job.

## Suggested manual checks

- Submit a valid request with several recipients.
- Submit an empty recipients list or invalid email; expect HTTP `422`.
- Poll `GET /jobs/{job_id}` and confirm counts reach the total.
- Download a successful certificate and open the PDF.
- Review the automated failure-isolation test.

## Limitations

- Background work runs in the API process and can be interrupted if the process stops.
- SQLite and local file storage are intended for this assignment/local demonstration, not multi-server production deployment.
- The single certificate design uses built-in Helvetica fonts; custom Unicode font embedding can be added if multilingual names are required.
