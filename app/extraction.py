import re
from datetime import date

from app.engine import OCRLine

BANK_MARKERS = {
    "scb": ("ธนาคารไทยพาณิชย์", "ไทยพาณิชย์", "siam commercial", "scb"),
    "krungthai": ("ธนาคารกรุงไทย", "กรุงไทย", "krungthai", "ktb"),
}
UNSUPPORTED_BANK_MARKERS = (
    "ธนาคาร", "kasikorn", "kbank", "กสิกรไทย", "bangkok bank", "ธนาคารกรุงเทพ",
    "กรุงเทพ", "กรุงศรี", "krungsri", "ออมสิน", "government savings",
    "ttb", "ทหารไทยธนชาต", "ธนาคารอาคารสงเคราะห์", "ธ.ก.ส.",
)
AMOUNT_LABELS = ("จำนวนเงิน", "ยอดเงิน", "amount", "transfer amount")
AMOUNT_PATTERN = re.compile(r"(?<!\d)(\d{1,3}(?:,\d{3})*(?:\.\d{2})|\d+\.\d{2})(?!\d)")
DATE_PATTERN = re.compile(r"(?<!\d)(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})(?!\d)")
TIME_PATTERN = re.compile(r"(?<!\d)([01]?\d|2[0-3]):([0-5]\d)(?!\d)")
REFERENCE_PATTERN = re.compile(r"(?i)(?:เลขที่รายการ|หมายเลขอ้างอิง|reference(?:\s*(?:no|number))?|ref\.?\s*no\.?)\s*[:#-]?\s*([A-Z0-9-]{6,})")


def _find_bank(lines: list[OCRLine]) -> tuple[str | None, float]:
    # OCR results are returned in reading order. Prefer the first bank name,
    # which is normally the issuing bank header, over recipient-bank mentions.
    for line in lines:
        normalized = line.text.casefold()
        if any(marker in normalized for marker in ("ผู้รับ", "recipient", "beneficiary")):
            continue
        matches = [
            bank for bank, markers in BANK_MARKERS.items()
            if any(marker.casefold() in normalized for marker in markers)
        ]
        if len(matches) == 1:
            return matches[0], line.confidence
        if len(matches) > 1:
            return None, 0.0
        if any(marker.casefold() in normalized for marker in UNSUPPORTED_BANK_MARKERS):
            return None, 0.0
    return None, 0.0


def _extract_amount(lines: list[OCRLine]) -> tuple[float | None, float, str | None]:
    for index, line in enumerate(lines):
        normalized = line.text.casefold()
        label = next((label for label in AMOUNT_LABELS if label in normalized), None)
        if label is not None:
            suffix = line.text[normalized.index(label) + len(label):]
            candidate = AMOUNT_PATTERN.search(suffix)
            source = line
            if candidate is None and index + 1 < len(lines):
                candidate = AMOUNT_PATTERN.search(lines[index + 1].text)
                source = lines[index + 1]
            if candidate:
                return float(candidate.group(1).replace(",", "")), source.confidence, source.text
    return None, 0.0, None


def _extract_date(text: str) -> tuple[str | None, float]:
    match = DATE_PATTERN.search(text)
    if not match:
        return None, 0.0
    day, month, raw_year = map(int, match.groups())
    if raw_year < 100:
        return None, 0.0
    year = raw_year
    if year >= 2400:
        year -= 543
    try:
        return date(year, month, day).isoformat(), 0.75
    except ValueError:
        return None, 0.0


def extract_fields(lines: list[OCRLine]) -> dict:
    text = "\n".join(line.text for line in lines)
    bank, bank_confidence = _find_bank(lines)
    amount, amount_confidence, amount_source = _extract_amount(lines)
    transaction_date, date_confidence = _extract_date(text)
    time_match = TIME_PATTERN.search(text)
    reference_match = REFERENCE_PATTERN.search(text)
    fields = {
        "documentType": {"value": "bank_transfer" if bank else "unknown", "confidence": bank_confidence},
        "bank": {"value": bank, "confidence": bank_confidence},
        "amount": {"value": amount, "confidence": amount_confidence, "sourceText": amount_source},
        "currency": {"value": "THB", "confidence": 1.0 if amount is not None else 0.0},
        "transactionDate": {"value": transaction_date, "confidence": date_confidence},
        "transactionTime": {
            "value": f"{time_match.group(1).zfill(2)}:{time_match.group(2)}" if time_match else None,
            "confidence": 0.75 if time_match else 0.0,
        },
        "referenceNo": {
            "value": reference_match.group(1) if reference_match else None,
            "confidence": 0.75 if reference_match else 0.0,
        },
    }
    required_confident = bank is not None and amount is not None and bank_confidence >= 0.65 and amount_confidence >= 0.65
    return {
        "documentType": "bank_transfer" if bank else "unknown",
        "bank": bank,
        "fields": fields,
        "rawText": text,
        "confidence": min(bank_confidence, amount_confidence) if required_confident else 0.0,
        "status": "needs_review",
        "requiresManualReview": True,
    }
