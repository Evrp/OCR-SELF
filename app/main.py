import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from io import BytesIO
from threading import BoundedSemaphore
from time import perf_counter
from typing import Annotated, Any, Literal

from PIL import Image, UnidentifiedImageError
from fastapi import FastAPI, File, Header, HTTPException, UploadFile
from pydantic import BaseModel, ConfigDict, Field

from app.config import get_settings
from app.engine import get_engine
from app.extraction import extract_fields


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield


app = FastAPI(
    title="Pure AI Thai Slip OCR API",
    summary="Self-hosted OCR for SCB and Krungthai bank transfer slips",
    description=(
        "Extracts draft transaction fields from Thai bank transfer slips. "
        "The first release targets Siam Commercial Bank (SCB) and Krungthai (KTB). "
        "Every result requires human review; do not create a transaction directly "
        "from OCR output. Images and recognized text may contain personal data."
    ),
    version="0.1.0",
    openapi_tags=[
        {"name": "Health", "description": "Service readiness."},
        {"name": "OCR", "description": "Thai bank slip recognition."},
    ],
    contact={"name": "Pure AI"},
    lifespan=lifespan,
)
logger = logging.getLogger("pure_ai_ocr")

# One PaddleOCR instance is used at a time. Keep one additional request queued;
# reject further work instead of allowing an unbounded executor backlog.
_OCR_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ocr")
_OCR_CAPACITY = BoundedSemaphore(2)


class OCRField(BaseModel):
    value: Any = Field(description="Extracted value, or null when not detected confidently.")
    confidence: float = Field(ge=0, le=1, description="Recognition confidence from 0 to 1.")
    sourceText: str | None = Field(default=None, description="OCR line supporting this value, when applicable.")


class OCRSlipResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "documentType": "bank_transfer",
                    "bank": "scb",
                    "fields": {
                        "documentType": {"value": "bank_transfer", "confidence": 0.96},
                        "bank": {"value": "scb", "confidence": 0.96},
                        "amount": {"value": 1250.0, "confidence": 0.97, "sourceText": "จำนวนเงิน 1,250.00"},
                        "currency": {"value": "THB", "confidence": 1.0},
                        "transactionDate": {"value": "2026-09-25", "confidence": 0.75},
                        "transactionTime": {"value": "14:32", "confidence": 0.94},
                        "referenceNo": {"value": "ABC123456789", "confidence": 0.91},
                    },
                    "rawText": "ตัวอย่างข้อความ OCR",
                    "confidence": 0.94,
                    "status": "needs_review",
                    "requiresManualReview": True,
                    "model": "PP-OCRv5-th",
                    "processingMs": 420,
                }
            ]
        }
    )
    documentType: Literal["bank_transfer", "unknown"]
    bank: Literal["scb", "krungthai"] | None = Field(
        description="Issuing bank detected from the slip. Null when unknown or ambiguous."
    )
    fields: dict[str, OCRField]
    rawText: str = Field(description="Recognized text. May contain personal data; handle securely.")
    confidence: float = Field(ge=0, le=1, description="Overall confidence for required fields.")
    status: Literal["needs_review"] = "needs_review"
    requiresManualReview: Literal[True] = True
    model: str
    processingMs: int = Field(ge=0)


class APIError(BaseModel):
    detail: str


@app.get("/health", tags=["Health"], summary="Check service liveness")
def health() -> dict[str, str]:
    """Return a lightweight liveness response; this does not load the OCR model."""
    return {"status": "ok"}


@app.post(
    "/v1/ocr/slip",
    tags=["OCR"],
    summary="OCR a Thai bank transfer slip",
    description=(
        "Accepts one JPEG, PNG, or WebP image. The initial scope is SCB and Krungthai. "
        "All extracted values are drafts and must be confirmed by a person. "
        "The response includes raw OCR text, which may contain personal data."
    ),
    response_model=OCRSlipResponse,
    responses={
        400: {"model": APIError, "description": "The upload is empty or is not a valid image."},
        401: {"model": APIError, "description": "The configured API key is missing or invalid."},
        413: {"model": APIError, "description": "The upload or image dimensions exceed the configured limit."},
        415: {"model": APIError, "description": "The file is not JPEG, PNG, or WebP."},
        503: {"model": APIError, "description": "The local OCR engine could not process the image."},
    },
)
async def recognize_slip(
    file: Annotated[
        UploadFile,
        File(
            description=(
                "Thai bank transfer slip image. Accepted content: JPEG, PNG, or WebP. "
                "Maximum size is configured by OCR_MAX_UPLOAD_BYTES (10 MiB by default)."
            ),
        ),
    ],
    x_api_key: Annotated[
        str | None,
        Header(
            alias="X-API-Key",
            description="Required only when the service is configured with OCR_API_KEY.",
        ),
    ] = None,
) -> OCRSlipResponse:
    """Recognize a slip and return field-level draft values for human review."""
    settings = get_settings()
    if settings.api_key and x_api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    if file.content_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise HTTPException(status_code=415, detail="Only JPEG, PNG, and WebP images are supported")
    image_bytes = await file.read(settings.max_upload_bytes + 1)
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Image is empty")
    if len(image_bytes) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="Image exceeds the upload size limit")
    try:
        with Image.open(BytesIO(image_bytes)) as image:
            if image.format not in {"JPEG", "PNG", "WEBP"}:
                raise HTTPException(status_code=415, detail="Unsupported image content")
            if image.width * image.height > settings.max_image_pixels * 4:
                raise HTTPException(status_code=413, detail="Image dimensions exceed the safety limit")
            image.verify()
    except Image.DecompressionBombError:
        raise HTTPException(status_code=413, detail="Image dimensions exceed the safety limit") from None
    except (UnidentifiedImageError, OSError):
        raise HTTPException(status_code=400, detail="Invalid image") from None

    started = perf_counter()
    if not _OCR_CAPACITY.acquire(blocking=False):
        raise HTTPException(status_code=503, detail="OCR capacity is temporarily full")
    try:
        concurrent_future = _OCR_EXECUTOR.submit(
            _recognize,
            settings.device,
            image_bytes,
            settings.max_image_pixels,
        )
    except Exception as exc:
        _OCR_CAPACITY.release()
        logger.exception("Could not submit an OCR request")
        raise HTTPException(status_code=503, detail="OCR engine is unavailable") from exc
    concurrent_future.add_done_callback(lambda _: _OCR_CAPACITY.release())
    try:
        lines = await asyncio.wrap_future(concurrent_future)
    except Exception as exc:
        logger.exception("OCR engine failed while processing an uploaded image")
        raise HTTPException(status_code=503, detail="OCR engine is unavailable") from exc
    result = extract_fields(lines)
    result["model"] = "PP-OCRv5-th"
    result["processingMs"] = round((perf_counter() - started) * 1000)
    return OCRSlipResponse(**result)


def _recognize(device: str, image_bytes: bytes, max_pixels: int):
    return get_engine(device).recognize(image_bytes, max_pixels)
