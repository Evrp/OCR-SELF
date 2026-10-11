from functools import lru_cache
import os


class Settings:
    max_upload_bytes: int = int(os.getenv("OCR_MAX_UPLOAD_BYTES", str(10 * 1024 * 1024)))
    max_image_pixels: int = int(os.getenv("OCR_MAX_IMAGE_PIXELS", "25000000"))
    device: str = os.getenv("OCR_DEVICE", "cpu")
    api_key: str = os.getenv("OCR_API_KEY", "")


@lru_cache
def get_settings() -> Settings:
    return Settings()
