from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
import logging

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import Base, build_database
from .models import CertificateRecord, GenerationJob
from .schemas import CertificateListOut, CertificateOut, CreateJobRequest, JobOut
from .certificate_generator import generate_certificate

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DATABASE_URL = f"sqlite:///{(BASE_DIR / 'certificate_generator.db').as_posix()}"
DEFAULT_STORAGE_DIR = BASE_DIR / "storage" / "certificates"

def create_app(
    database_url: str = DEFAULT_DATABASE_URL,
    storage_dir: str | Path = DEFAULT_STORAGE_DIR,
    generator=generate_certificate,
) -> FastAPI:
    storage_path = Path(storage_dir)
    storage_path.mkdir(parents=True, exist_ok=True)
    engine, SessionLocal = build_database(database_url)
    Base.metadata.create_all(bind=engine)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        yield
        engine.dispose()

    app = FastAPI(
        title="Bulk Certificate Generator API",
        description="Create bulk certificate jobs, track progress, and download generated PDF certificates.",
        version="1.0.0",
        lifespan=lifespan,
    )
    app.state.session_local = SessionLocal
    app.state.storage_path = storage_path
    app.state.certificate_generator = generator
    app.state.engine = engine

    def get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    def serialize_job(job: GenerationJob, include_certificates: bool = False) -> dict:
        total = job.total_count
        certificates = None
        if include_certificates:
            certificates = [
                CertificateOut(
                    id=cert.id, recipient_name=cert.recipient_name,
                    recipient_email=cert.recipient_email, status=cert.status,
                    error_message=cert.error_message,
                )
                for cert in job.certificates
            ]
        return {
            "id": job.id,
            "event_name": job.event_name,
            "issuer_name": job.issuer_name,
            "certificate_date": job.certificate_date,
            "status": job.status,
            "total_count": total,
            "processed_count": job.processed_count,
            "success_count": job.success_count,
            "failed_count": job.failed_count,
            "progress_percent": round(job.processed_count * 100 / total, 2) if total else 0.0,
            "created_at": job.created_at.isoformat(),
            "updated_at": job.updated_at.isoformat(),
            "certificates": certificates,
        }

    def process_job(job_id: str) -> None:
        """Process each recipient independently; a single failure does not abort the job."""
        db: Session = SessionLocal()
        try:
            job = db.get(GenerationJob, job_id)
            if job is None:
                logger.error("Generation job %s disappeared before processing", job_id)
                return
            job.status = "running"
            job.updated_at = datetime.now(timezone.utc)
            db.commit()

            cert_ids = list(db.scalars(
                select(CertificateRecord.id).where(CertificateRecord.job_id == job_id)
            ).all())
            for cert_id in cert_ids:
                cert = db.get(CertificateRecord, cert_id)
                job = db.get(GenerationJob, job_id)
                if cert is None or job is None:
                    continue
                try:
                    cert.status = "processing"
                    db.commit()
                    filename = f"{cert.id}.pdf"
                    output_path = storage_path / filename
                    app.state.certificate_generator(
                        output_path=output_path,
                        recipient_name=cert.recipient_name,
                        event_name=job.event_name,
                        issuer_name=job.issuer_name,
                        certificate_date=job.certificate_date,
                    )
                    cert.status = "succeeded"
                    cert.file_path = str(output_path.resolve())
                    cert.error_message = None
                    job.success_count += 1
                except Exception as exc:
                    logger.exception("Certificate generation failed for %s", cert_id)
                    cert.status = "failed"
                    cert.error_message = str(exc)[:1000] or "Certificate generation failed"
                    cert.file_path = None
                    job.failed_count += 1
                finally:
                    job.processed_count += 1
                    job.updated_at = datetime.now(timezone.utc)
                    db.commit()

            job = db.get(GenerationJob, job_id)
            if job:
                if job.failed_count and job.success_count:
                    job.status = "completed_with_errors"
                elif job.failed_count and not job.success_count:
                    job.status = "failed"
                else:
                    job.status = "completed"
                job.updated_at = datetime.now(timezone.utc)
                db.commit()
        except Exception as exc:
            logger.exception("Unexpected job-level error for %s", job_id)
            db.rollback()
            job = db.get(GenerationJob, job_id)
            if job:
                job.status = "failed"
                job.error_message = str(exc)[:1000]
                job.updated_at = datetime.now(timezone.utc)
                db.commit()
        finally:
            db.close()

    @app.get("/health", tags=["System"])
    def health():
        return {"status": "ok"}

    @app.post("/jobs", response_model=JobOut, status_code=status.HTTP_202_ACCEPTED, tags=["Jobs"])
    def create_job(payload: CreateJobRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
        job_id = str(uuid4())
        job = GenerationJob(
            id=job_id,
            event_name=payload.event_name,
            issuer_name=payload.issuer_name,
            certificate_date=payload.certificate_date.isoformat(),
            status="queued",
            total_count=len(payload.recipients),
            processed_count=0,
            success_count=0,
            failed_count=0,
        )
        db.add(job)
        for recipient in payload.recipients:
            db.add(CertificateRecord(
                id=str(uuid4()), job_id=job_id,
                recipient_name=recipient.name,
                recipient_email=str(recipient.email) if recipient.email else None,
                status="pending",
            ))
        db.commit()
        db.refresh(job)
        background_tasks.add_task(process_job, job_id)
        return serialize_job(job, include_certificates=True)

    @app.get("/jobs/{job_id}", response_model=JobOut, tags=["Jobs"])
    def get_job(job_id: str, db: Session = Depends(get_db)):
        job = db.get(GenerationJob, job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Generation job not found")
        return serialize_job(job, include_certificates=True)

    @app.get("/jobs/{job_id}/certificates", response_model=CertificateListOut, tags=["Certificates"])
    def list_certificates(job_id: str, db: Session = Depends(get_db)):
        job = db.get(GenerationJob, job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Generation job not found")
        certs = list(db.scalars(
            select(CertificateRecord).where(CertificateRecord.job_id == job_id)
            .order_by(CertificateRecord.created_at)
        ).all())
        return {
            "job_id": job_id,
            "total": len(certs),
            "certificates": [
                CertificateOut(
                    id=c.id, recipient_name=c.recipient_name, recipient_email=c.recipient_email,
                    status=c.status, error_message=c.error_message,
                ) for c in certs
            ],
        }

    @app.get("/certificates/{certificate_id}", tags=["Certificates"])
    def download_certificate(certificate_id: str, db: Session = Depends(get_db)):
        cert = db.get(CertificateRecord, certificate_id)
        if not cert:
            raise HTTPException(status_code=404, detail="Certificate not found")
        if cert.status != "succeeded" or not cert.file_path:
            if cert.status == "failed":
                raise HTTPException(status_code=409, detail="This certificate failed to generate")
            raise HTTPException(status_code=409, detail="Certificate is not ready yet")
        path = Path(cert.file_path)
        if not path.is_file():
            raise HTTPException(status_code=404, detail="Generated certificate file is missing")
        return FileResponse(
            path=path, media_type="application/pdf",
            filename=f"certificate_{cert.recipient_name.replace(' ', '_')}_{cert.id[:8]}.pdf",
        )

    return app

app = create_app()
