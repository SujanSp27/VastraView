import logging
import time
from contextlib import asynccontextmanager
from threading import BoundedSemaphore
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from pymongo.errors import PyMongoError
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session
from starlette.datastructures import UploadFile as MultipartUpload

from backend.app.accounts.lifecycle import router as lifecycle_router
from backend.app.accounts.locks import account_operation
from backend.app.accounts.router import account_db
from backend.app.accounts.router import router as account_router
from backend.app.accounts.security import csrf_guard, require_admin, throttle
from backend.app.anthropometry.repository import repository as measurement_repository
from backend.app.anthropometry.router import get_measurement_service
from backend.app.anthropometry.router import router as measurement_router
from backend.app.catalog import router as catalog_router
from backend.app.charts import chart_dict, create_chart, latest_chart, seed_database
from backend.app.colab_connection import ColabConnection
from backend.app.config import ROOT, settings
from backend.app.db import SessionLocal, engine, get_db
from backend.app.garments import router as garment_router
from backend.app.health import router as health_router
from backend.app.jobs import TryOnJobs
from backend.app.models import Brand, ChartVersion, Run
from backend.app.online_vton import normalized_image
from backend.app.pipeline import TryOnPipeline
from backend.app.private_data import GUEST_COOKIE, authenticated_owner, owned_run, principal
from backend.app.private_data import router as private_router
from backend.app.schemas import (
    BrandCreate,
    ChartCreate,
    RunPage,
    RunStatus,
    SizingRequest,
    TryOnMode,
)
from backend.app.storage import AssetStore
from ml.errors import PipelineError
from ml.sizing.engine import Category, Fit, recommend
from ml.vton.categories import GarmentCategory

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)
store = AssetStore(settings.asset_root)
pipeline = TryOnPipeline(store)
connection = ColabConnection(pipeline.worker)
capacity = BoundedSemaphore(1)
jobs = TryOnJobs(ROOT / ".runtime/tryon-jobs", capacity)


@asynccontextmanager
async def lifespan(app: FastAPI):
    jobs.recover_interrupted()
    try:
        with SessionLocal() as db:
            seed_database(db)
    except SQLAlchemyError:
        # The independent MongoDB APIs should remain usable during a SQL outage.
        logger.error("PostgreSQL startup check failed; legacy sizing and try-on are unavailable.")
    connection.start()
    try:
        yield
    finally:
        connection.close()
        jobs.close()
        pipeline.worker.close()
        if get_measurement_service.cache_info().currsize:
            get_measurement_service().detector.close()
            get_measurement_service.cache_clear()
        measurement_repository.close()


app = FastAPI(title="VastraView API", version="0.3.0", lifespan=lifespan,
              description="Private Colab 2D try-on, CPU body estimates, and MongoDB-backed brand sizing. Single-process local prototype.")
app.state.tryon_connection = connection
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "Authorization", "X-Admin-Token", "Prefer", "Idempotency-Key"],
    expose_headers=["Location", "X-Request-ID", "Retry-After"],
)
annotation_root = settings.measurement_output_root / "annotated"
annotation_root.mkdir(parents=True, exist_ok=True)
app.include_router(measurement_router)
app.include_router(health_router)
app.include_router(garment_router)
app.include_router(account_router)
app.include_router(lifecycle_router)
app.include_router(catalog_router)


@app.get("/assets/garments/{filename}")
def static_garment_asset(filename: str):
    root = (ROOT / "assets/garments").resolve()
    path = (root / filename).resolve()
    if not (path.is_file() and path.is_relative_to(root)):
        alt_root = (ROOT / "data/raw/assets/garments").resolve()
        alt_path = (alt_root / filename).resolve()
        if alt_path.is_file() and alt_path.is_relative_to(alt_root):
            path = alt_path
        else:
            raise HTTPException(404, "Garment image not found")
    media_type = "image/jpeg" if path.suffix.lower() in {".jpg", ".jpeg"} else "application/octet-stream"
    return FileResponse(path, media_type=media_type)


app.include_router(private_router)


@app.middleware("http")
async def limit_request(request, call_next):
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        try:
            csrf_guard(request)
        except HTTPException as exc:
            return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    length = request.headers.get("content-length")
    if request.method in {"POST", "PUT", "PATCH", "DELETE"} and "application/json" in request.headers.get("content-type", ""):
        limit = 1024 * 1024
        payload = bytearray()
        async for chunk in request.stream():
            if len(payload) + len(chunk) > limit:
                return JSONResponse(status_code=413, content={"detail": "JSON requests must be smaller than 1 MB."})
            payload.extend(chunk)
        # CachedRequest replays the bounded bytes to downstream parsers, including
        # requests streamed without Content-Length.
        request._body = bytes(payload)
    if request.url.path.startswith(("/api/v1/auth/", "/api/v1/profile")) and request.method in {"POST", "PATCH"}:
        if length and (not length.isdigit() or int(length) > 1024 * 1024):
            return JSONResponse(status_code=413, content={"error": {"code": "request_too_large", "message": "Account requests must be smaller than 1 MB."}})
    upload_paths = {"/api/tryon": 2, "/api/v1/measurements/extract": 1,
                    "/api/v1/measurements/extract-and-recommend": 1}
    if request.url.path in upload_paths and request.method == "POST":
        if not length:
            return JSONResponse(
                status_code=411,
                content={
                    "error": {
                        "code": "length_required",
                        "message": "Content-Length is required for image uploads.",
                    }
                },
            )
        if not length.isdigit() or int(length) > (
            settings.max_upload_mb * upload_paths[request.url.path] + 1
        ) * 1024 * 1024:
            return JSONResponse(
                status_code=413,
                content={
                    "error": {
                        "code": "upload_too_large",
                        "message": "Request exceeds the upload limit.",
                    }
                },
            )
    return await call_next(request)


@app.middleware("http")
async def request_metadata(request, call_next):
    request.state.request_id = uuid4().hex
    start = time.perf_counter()
    async with account_operation(request):
        response = await call_next(request)
    if getattr(request.state, "guest_token", None):
        response.set_cookie(GUEST_COOKIE, request.state.guest_token, httponly=True,
                            secure=settings.auth_cookie_secure, samesite="strict", path="/",
                            max_age=settings.guest_retention_hours * 3600)
    response.headers["X-Request-ID"] = request.state.request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "same-origin"
    if settings.environment == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    if request.url.path.startswith(("/api/v1/auth", "/api/v1/profile", "/api/v1/history", "/api/v1/favorites",
                                    "/api/v1/measurements", "/api/tryon", "/api/runs", "/assets", "/static/annotated")):
        response.headers["Cache-Control"] = "no-store"
    if response.status_code in (429, 503):
        response.headers["Retry-After"] = "5"
    if request.url.path.startswith("/api/"):
        logger.info("request=%s method=%s status=%s seconds=%.3f", request.state.request_id,
                    request.method, response.status_code, time.perf_counter() - start)
    return response


@app.exception_handler(PipelineError)
async def pipeline_error(_, exc: PipelineError):
    return JSONResponse(
        status_code=exc.status_code, content={"error": {"code": exc.code, "message": str(exc)}}
    )


@app.exception_handler(IntegrityError)
async def integrity_error(_, exc):
    return JSONResponse(
        status_code=409,
        content={
            "error": {
                "code": "conflict",
                "message": "A brand or chart version with these identifiers already exists.",
            }
        },
    )


@app.exception_handler(SQLAlchemyError)
async def database_error(_, exc):
    logger.error("PostgreSQL request failed (%s)", type(exc).__name__)
    return JSONResponse(status_code=503, content={"error": {
        "code": "database_unavailable", "message": "The application database is unavailable; retry when it is running."}})


@app.exception_handler(PyMongoError)
async def account_database_error(_, exc):
    logger.error("Account database request failed (%s)", type(exc).__name__)
    return JSONResponse(status_code=503, content={"error": {
        "code": "account_database_unavailable", "message": "The account database is unavailable. Please retry shortly."}})


@app.exception_handler(Exception)
async def unexpected_error(request, exc):
    request_id = getattr(request.state, "request_id", uuid4().hex)
    logger.error("Unexpected API error request=%s type=%s", request_id, type(exc).__name__)
    return JSONResponse(status_code=500, headers={"X-Request-ID": request_id}, content={"error": {
        "code": "internal_error", "message": "An unexpected error occurred. Use the request ID to locate the server log.",
        "request_id": request_id}})


def admin(x_admin_token: str = Header(default="")):
    require_admin(x_admin_token)


@app.get("/api/health")
def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {
        "status": "ok",
        "database": engine.dialect.name,
        "tryonModes": ["2d"],
        "vton2d": connection.snapshot(),
        "scope": "Online GPU photo try-on; independent measured-input brand sizing",
    }


@app.get("/api/brands")
def brands(db: Session = Depends(get_db)):
    return [
        {"id": b.id, "name": b.name, "slug": b.slug, "isDemo": b.is_demo}
        for b in db.scalars(select(Brand).order_by(Brand.id))
    ]


@app.get("/api/tryon/availability")
def tryon_availability():
    # Independent from PostgreSQL and the inference queue, always fast.
    return connection.snapshot()


@app.post("/api/tryon/retry", status_code=202, dependencies=[Depends(authenticated_owner)])
def retry_tryon_connection():
    return connection.retry()


class ColabConnectPayload(BaseModel):
    connection: str = Field(min_length=1, max_length=4096)


@app.post("/api/tryon/connect", status_code=200, dependencies=[Depends(authenticated_owner)])
def connect_tryon(payload: ColabConnectPayload, x_admin_token: str = Header(default="")):
    if settings.environment == "production":
        require_admin(x_admin_token)
    import json
    import re
    raw = payload.connection.strip()
    url, token = None, None
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            if "connection" in parsed and isinstance(parsed["connection"], dict):
                parsed = parsed["connection"]
            url = parsed.get("url")
            token = parsed.get("token")
    except (ValueError, TypeError):
        pass
    if url is not None and not isinstance(url, str):
        raise HTTPException(400, "Invalid worker connection.")
    if token is not None and not isinstance(token, str):
        raise HTTPException(400, "Invalid worker connection.")
    if not url:
        url_match = re.search(r"https://[a-zA-Z0-9-]+\.gradio\.live", raw)
        if url_match:
            url = url_match.group(0)
    if not token:
        remaining = raw.replace(url, "") if url else raw
        token_match = re.search(r"[A-Za-z0-9_-]{32,80}", remaining)
        if token_match:
            token = token_match.group(0)
    if not url or not token:
        raise HTTPException(
            400,
            "Could not find a valid Gradio URL and private token. Please paste the full connection JSON or URL and token."
        )
    try:
        snapshot = connection.adopt_credentials(url, token)
        return {"success": True, "snapshot": snapshot}
    except Exception as exc:
        logger.warning("Manual worker connection rejected (%s)", type(exc).__name__)
        raise HTTPException(400, "The worker could not be verified. Check the connection details and retry.") from exc


@app.post("/api/brands", status_code=201, dependencies=[Depends(admin)])
def add_brand(data: BrandCreate, db: Session = Depends(get_db)):
    brand = Brand(name=data.name, slug=data.slug, is_demo=data.isDemo)
    db.add(brand)
    db.commit()
    return {"id": brand.id, **data.model_dump()}


@app.get("/api/brands/{brand_id}/charts")
def get_chart(
    brand_id: int,
    garmentCategory: Category,
    version: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
):
    return chart_dict(latest_chart(db, brand_id, garmentCategory.value, version))


@app.get("/api/brands/{brand_id}/chart-versions")
def versions(brand_id: int, garmentCategory: Category, db: Session = Depends(get_db)):
    return [
        {"version": c.version, "source": c.source, "createdAt": c.created_at.isoformat()}
        for c in db.scalars(
            select(ChartVersion)
            .where(
                ChartVersion.brand_id == brand_id,
                ChartVersion.garment_category == garmentCategory.value,
            )
            .order_by(ChartVersion.version.desc())
        )
    ]


@app.post("/api/brands/{brand_id}/charts", status_code=201, dependencies=[Depends(admin)])
@app.put("/api/brands/{brand_id}/charts", status_code=201, dependencies=[Depends(admin)])
def add_chart(brand_id: int, data: ChartCreate, db: Session = Depends(get_db)):
    chart = create_chart(db, brand_id, data)
    db.commit()
    return chart_dict(chart)


@app.post("/api/sizing/recommend")
def sizing(data: SizingRequest, db: Session = Depends(get_db)):
    chart = latest_chart(db, data.brandId, data.garmentCategory.value)
    result = recommend(
        data.measurements.model_dump(exclude_none=True),
        chart_dict(chart)["sizes"],
        data.garmentCategory.value,
        data.fitPreference.value,
    )
    return {**result, "chartVersion": chart.version, "chartSource": chart.source}


def upload_bytes(upload: UploadFile) -> bytes:
    limit = settings.max_upload_mb * 1024 * 1024
    data = upload.file.read(limit + 1)
    if len(data) > limit:
        raise PipelineError(
            "upload_too_large", f"Each image must be below {settings.max_upload_mb} MB.", 413
        )
    return data


def require_tryon_ready():
    status = pipeline.worker.availability(check_connection=True)
    if not status['available']:
        connection.retry()
        raise PipelineError('online_gpu_unavailable', connection.snapshot()['reason'] or
                            'The Colab model is unavailable. Recovery has been requested; retry shortly.', 503)


async def require_single_garment(request: Request):
    """Reject ambiguous/legacy multipart inputs before any inference is scheduled."""
    form = await request.form()
    retired_fields = {"bottomwearImage", "bottomwearCategory", "bottomwearPhotoType",
                      "bottomwearProductId", "topwearImage", "topwearRunId"}
    for key in form:
        values = form.getlist(key)
        if (key in retired_fields or len(values) != 1
                or (isinstance(values[0], MultipartUpload) and key not in {"personImage", "garmentImage"})):
            raise PipelineError("single_garment_only", "Upload exactly one person image and one garment image.", 422)


@app.post("/api/tryon", dependencies=[Depends(require_single_garment)])
def tryon(
    request: Request,
    personImage: UploadFile = File(),
    garmentImage: UploadFile = File(),
    brandId: int | None = Form(default=None, gt=0),
    garmentCategory: GarmentCategory = Form(),
    fitPreference: Fit = Form(Fit.regular),
    tryonMode: TryOnMode = Form(TryOnMode.two_d),
    garmentPhotoType: str = Form(default="flat-lay", pattern="^(flat-lay|model)$"),
    productId: str | None = Form(default=None, pattern="^[a-z0-9][a-z0-9-]{1,79}$"),
    prefer: str = Header(default=""),
    idempotency_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
    owner: str = Depends(authenticated_owner),
    accounts=Depends(account_db),
):
    throttle(accounts, request, "tryon", owner, maximum=200 if settings.environment == "development" else 20)
    if brandId is not None and db.get(Brand, brandId) is None:
        raise PipelineError("brand_missing", "The selected brand does not exist.", 404)
    person_data, garment_data = upload_bytes(personImage), upload_bytes(garmentImage)
    garment_descriptor = None
    if productId:
        from backend.app.wardrobe import validate_catalog_submission
        garment_descriptor = validate_catalog_submission(accounts, productId, garment_data, garmentCategory.value, garmentPhotoType)
    if prefer == "respond-async":
        # Image generation is independent of available sizing charts.
        parameters = {
            "brand_id": brandId, "category": garmentCategory.value, "fit": fitPreference.value,
            "photo_type": garmentPhotoType,
            "owner": owner,
        }
        if garment_descriptor is not None:
            parameters["garment_descriptor"] = garment_descriptor

        def work():
            # A request-scoped database session cannot cross into the worker thread.
            with SessionLocal() as worker_db:
                return pipeline.run(worker_db, person_data, garment_data, **parameters)

        def preflight():
            normalized_image(person_data)
            normalized_image(garment_data)
            require_tryon_ready()

        state = jobs.submit(person_data, garment_data, parameters, work, idempotency_key, preflight=preflight)
        return JSONResponse(status_code=202, content=state, headers={"Location": state["statusUrl"]})
    if not capacity.acquire(blocking=False):
        raise PipelineError("busy", "Another try-on is running. Retry after it finishes.", 429)
    try:
        require_tryon_ready()
        return pipeline.run(
            db,
            person_data,
            garment_data,
            brandId,
            garmentCategory.value,
            fitPreference.value,
            photo_type=garmentPhotoType,
            owner=owner,
            garment_descriptor=garment_descriptor,
        )
    finally:
        capacity.release()


@app.get("/api/tryon/jobs/{job_id}")
def job_status(job_id: UUID, owner=Depends(principal)):
    return jobs.get(job_id, owner=owner)


async def require_continuation_form(request: Request):
    form = await request.form()
    allowed = {"sourceRunId", "garmentImage", "garmentCategory", "garmentPhotoType", "productId"}
    if any(key not in allowed or len(form.getlist(key)) != 1 for key in form):
        raise PipelineError("outfit_inputs", "Select one saved render and one new garment.", 422)


@app.post("/api/tryon/apply", dependencies=[Depends(require_continuation_form)])
def apply_to_render(
    request: Request,
    sourceRunId: UUID = Form(),
    garmentImage: UploadFile = File(),
    garmentCategory: GarmentCategory = Form(),
    garmentPhotoType: str = Form(default="flat-lay", pattern="^(flat-lay|model)$"),
    productId: str | None = Form(default=None, pattern="^[a-z0-9][a-z0-9-]{1,79}$"),
    idempotency_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
    owner: str = Depends(authenticated_owner),
    accounts=Depends(account_db),
):
    from backend.app.outfit_continuation import apply_garment, continuation_input
    from backend.app.wardrobe import validate_catalog_submission

    throttle(accounts, request, "tryon", owner, maximum=200 if settings.environment == "development" else 20)
    garment = upload_bytes(garmentImage)
    descriptor = validate_catalog_submission(accounts, productId, garment, garmentCategory.value, garmentPhotoType) if productId else None
    person = continuation_input(db, pipeline, sourceRunId, owner, garmentCategory.value)
    parameters = {"source_run_id": str(sourceRunId), "category": garmentCategory.value,
                  "photo_type": garmentPhotoType, "owner": owner, "garment_descriptor": descriptor}

    def work():
        with SessionLocal() as worker_db:
            return apply_garment(pipeline, worker_db, person, garment, **parameters)

    def preflight():
        normalized_image(person)
        normalized_image(garment)
        require_tryon_ready()

    state = jobs.submit(person, garment, parameters, work, idempotency_key, preflight=preflight)
    return JSONResponse(status_code=202, content=state, headers={"Location": state["statusUrl"]})


@app.post("/api/tryon/outfit", deprecated=True, include_in_schema=False)
def retired_outfit_tryon(owner: str = Depends(authenticated_owner)):
    # Preserve an actionable response for old clients, never schedule two generations.
    raise PipelineError("single_garment_only",
                        "Combined try-on has been retired. Submit one person and one garment to /api/tryon.", 410)


@app.get("/api/runs", response_model=RunPage, dependencies=[Depends(admin)])
def list_runs(limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0),
              status: RunStatus | None = None, db: Session = Depends(get_db)):
    query = select(Run)
    count = select(func.count()).select_from(Run)
    if status is not None:
        query = query.where(Run.status == status)
        count = count.where(Run.status == status)
    rows = db.scalars(query.order_by(Run.created_at.desc(), Run.id).offset(offset).limit(limit))
    return {"items": [{"id": row.id, "status": row.status, "created_at": row.created_at} for row in rows],
            "total": db.scalar(count), "limit": limit, "offset": offset}


@app.get("/api/runs/{run_id}")
def get_run(run_id: UUID, db: Session = Depends(get_db), owner=Depends(principal)):
    run = owned_run(db, run_id, owner)
    return {"id": run.id, "status": run.status, "metadata": {k: v for k, v in run.metadata_json.items() if k != "owner"}}


@app.delete("/api/runs/{run_id}", status_code=204, dependencies=[Depends(admin)])
def delete_run(run_id: UUID, db: Session = Depends(get_db)):
    run = db.get(Run, str(run_id))
    if not run:
        raise HTTPException(404, "Run not found")
    if run.status == "processing":
        raise HTTPException(409, "Cannot delete a running job")
    store.delete(str(run_id))
    db.delete(run)
    db.commit()


def sample_person_path(gender: str):
    candidates = (
        ("assets/Model/studio-person.png", "assets/Model/studio-person.jpg", "data/raw/studio-person.jpg")
        if gender == "male" else
        ("assets/Model/vastraview_female_model.png", "data/raw/vastraview_female_model.png")
    )
    return next((ROOT / path for path in candidates if (ROOT / path).is_file()), None)


@app.get("/api/samples/models")
def sample_models():
    """Return available sample models for virtual try-on."""
    if settings.environment == "production":
        return []
    models = [
        {
            "id": "male",
            "name": "Male Model",
            "gender": "male",
            "url": "/api/samples/person-male",
            "filename": "studio-person.jpg",
            "description": "Standard athletic male model (180 cm)",
        },
        {
            "id": "female",
            "name": "Female Model",
            "gender": "female",
            "url": "/api/samples/person-female",
            "filename": "vastraview_female_model.png",
            "description": "Standard elegant female model (168 cm)",
        },
    ]
    available = []
    for model in models:
        target = sample_person_path(model["id"])
        if target is not None:
            available.append({**model, "filename": target.name})
    return available


@app.get("/api/samples/{kind}")
def sample(kind: str):
    if settings.environment == "production":
        raise HTTPException(404, "Research samples are not published in production.")
    files = {
        "person": "studio-person.jpg",
        "male": "studio-person.jpg",
        "person-male": "studio-person.jpg",
        "female": "vastraview_female_model.png",
        "person-female": "vastraview_female_model.png",
        "garment": "garment-demo.png",
        "polo": "sage-polo.jpg",
    }
    if kind not in files:
        raise HTTPException(404, "Sample not available")
    if "female" in kind:
        target = sample_person_path("female")
    elif "male" in kind or kind == "person":
        target = sample_person_path("male")
    else:
        target = ROOT / "data/raw" / files[kind]
    if target is None or not target.is_file():
        raise HTTPException(404, "Sample not available")
    return FileResponse(
        target,
        media_type="image/png" if target.suffix.lower() == ".png" else "image/jpeg",
        headers={"Cache-Control": "no-cache, must-revalidate"},
    )


@app.get("/api/v1/public-config")
def public_config():
    return {
        "sample_photos": settings.environment != "production" and any(
            sample_person_path(gender) is not None for gender in ("male", "female")
        ),
        "email_verification_required": settings.auth_require_verification,
        "manual_worker_connection": settings.environment != "production",
        "guest_retention_hours": settings.guest_retention_hours,
        "generated_retention_days": settings.private_retention_days,
    }
