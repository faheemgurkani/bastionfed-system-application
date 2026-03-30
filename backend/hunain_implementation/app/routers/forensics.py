import json
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status

from app.auth.deps import AuthContext, require_read_auth
from app.errors import api_error
from app.ml.inference import models_loaded, predict_from_image
from app.models.api import MalwareSampleListResponse
from app.models.domain import MalwareSample, RCAReport
from app.store.memory import state

router = APIRouter(tags=["forensics"])


@router.get("/forensics/samples", response_model=MalwareSampleListResponse)
def list_samples(
    _auth: Annotated[AuthContext, Depends(require_read_auth)],
    limit: int = 50,
    cursor: str | None = None,
    sample_status: str | None = Query(None, alias="status"),
    family: str | None = None,
):
    items, next_cursor, total = state.list_samples(
        limit=min(limit, 200),
        cursor=cursor,
        status=sample_status,
        family=family,
    )
    return MalwareSampleListResponse(items=items, next_cursor=next_cursor, total=total)


@router.get("/forensics/rca/{rca_id}", response_model=RCAReport)
def get_rca(
    rca_id: str,
    _auth: Annotated[AuthContext, Depends(require_read_auth)],
):
    r = state.get_rca(rca_id)
    if not r:
        raise api_error(status.HTTP_404_NOT_FOUND, "RCA report not found", "RCA_NOT_FOUND")
    return r


@router.get("/forensics/samples/{sample_id}", response_model=MalwareSample)
def get_sample(
    sample_id: str,
    _auth: Annotated[AuthContext, Depends(require_read_auth)],
):
    s = state.get_sample(sample_id)
    if not s:
        raise api_error(status.HTTP_404_NOT_FOUND, "Sample not found", "SAMPLE_NOT_FOUND")
    return s


@router.post("/forensics/analyze")
async def analyze(
    _auth: Annotated[AuthContext, Depends(require_read_auth)],
    file: Optional[UploadFile] = File(None, description="Bi-gram DCT PNG image"),
    fv_file: Optional[UploadFile] = File(None, description="JSON file with 320-dim feature vector array"),
    sha256: Optional[str] = Form(None, description="SHA256 hash to look up FV from dataset"),
):
    if not models_loaded():
        raise api_error(status.HTTP_503_SERVICE_UNAVAILABLE, "ML models not loaded", "MODELS_NOT_READY")

    # --- Image ---
    image_bytes: bytes | None = None
    if file and file.size:
        if not file.content_type or not file.content_type.startswith("image/"):
            raise api_error(status.HTTP_422_UNPROCESSABLE_ENTITY, "Image file must be PNG", "INVALID_FILE_TYPE")
        image_bytes = await file.read()
        if len(image_bytes) == 0:
            image_bytes = None

    # --- Feature Vector ---
    feature_vector: list[float] | None = None

    # Priority 1: uploaded FV JSON file
    if fv_file and fv_file.size:
        raw = await fv_file.read()
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list) and len(parsed) == 320:
                feature_vector = [float(x) for x in parsed]
            elif isinstance(parsed, dict) and "features" in parsed:
                feature_vector = [float(x) for x in parsed["features"]]
            else:
                raise api_error(status.HTTP_422_UNPROCESSABLE_ENTITY, "FV JSON must be an array of 320 floats or {features: [...]}", "INVALID_FV")
        except (json.JSONDecodeError, ValueError, TypeError):
            raise api_error(status.HTTP_422_UNPROCESSABLE_ENTITY, "Invalid FV JSON file", "INVALID_FV")

    # Priority 2: sha256 form field → lookup from dataset
    if feature_vector is None and sha256:
        sha256 = sha256.strip().lower()
        from app.ml.data import get_feature_vector
        feature_vector = get_feature_vector(sha256)

    # Priority 3: extract sha256 from image filename
    extracted_sha: str | None = None
    if feature_vector is None and file and file.filename:
        extracted_sha = file.filename.split("_")[0].split(".")[0].lower()
        if extracted_sha and len(extracted_sha) == 64:
            from app.ml.data import get_feature_vector
            feature_vector = get_feature_vector(extracted_sha)

    if not image_bytes and feature_vector is None:
        raise api_error(status.HTTP_422_UNPROCESSABLE_ENTITY, "Provide at least an image or a feature vector (sha256 / FV file)", "NO_INPUT")

    active_model = state.active_model_name
    result = predict_from_image(image_bytes, feature_vector=feature_vector, model_name=active_model)
    result["sha256"] = sha256 or extracted_sha
    return result
