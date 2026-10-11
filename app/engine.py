from dataclasses import dataclass
from functools import lru_cache
from io import BytesIO

import numpy as np
from PIL import Image, ImageOps


@dataclass(frozen=True)
class OCRLine:
    text: str
    confidence: float


class PaddleThaiOCREngine:
    """Lazy-loaded PaddleOCR PP-OCRv5 Thai recognition pipeline."""

    def __init__(self, device: str = "cpu") -> None:
        from paddleocr import PaddleOCR

        self._ocr = PaddleOCR(
            lang="th",
            device=device,
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
        )

    def recognize(self, image_bytes: bytes, max_pixels: int) -> list[OCRLine]:
        with Image.open(BytesIO(image_bytes)) as image:
            image = ImageOps.exif_transpose(image).convert("RGB")
            if image.width * image.height > max_pixels:
                scale = (max_pixels / (image.width * image.height)) ** 0.5
                image = image.resize((int(image.width * scale), int(image.height * scale)))
            image_array = np.asarray(image)

        predictions = self._ocr.predict(image_array)
        lines: list[OCRLine] = []
        for prediction in predictions:
            data = prediction.json
            if isinstance(data, dict) and "res" in data:
                data = data["res"]
            texts = data.get("rec_texts", [])
            scores = data.get("rec_scores", [])
            for index, text in enumerate(texts):
                clean_text = str(text).strip()
                if clean_text:
                    score = float(scores[index]) if index < len(scores) else 0.0
                    lines.append(OCRLine(clean_text, max(0.0, min(1.0, score))))
        return lines


@lru_cache
def get_engine(device: str) -> PaddleThaiOCREngine:
    return PaddleThaiOCREngine(device=device)
