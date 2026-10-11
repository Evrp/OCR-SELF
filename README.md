# Pure AI Thai Slip OCR

บริการ OCR ที่รันโมเดลเองสำหรับสลิปโอนเงิน SCB และกรุงไทย เริ่มต้นด้วย PaddleOCR PP-OCRv5 รุ่นภาษาไทย แล้วดึง field ด้วย parser แบบกำหนดกฎ ผลลัพธ์ทุกภาพยังเป็น `needs_review` จนกว่าจะผ่านการตรวจและยืนยันโดยผู้ใช้

## วิธีรันโปรเจกต์

เลือกได้ 2 วิธี: รันตรงใน Python environment หรือใช้ Docker แบบ CPU. Docker image กำหนดเป็น `linux/amd64` เพราะ PaddleOCR 3.3.0 มีปัญหา SIGSEGV ขณะ initialize บน ARM64 ในบางสภาพแวดล้อม; Apple Silicon จะรันผ่าน emulation ซึ่งอาจช้ากว่าเครื่อง x86_64.

### รันด้วย Python

ต้องใช้ Python 3.11 หรือ 3.12 และติดตั้ง PaddlePaddle/PaddleOCR ตามแพลตฟอร์มที่ใช้:

โปรเจกต์ pin PaddleOCR 3.3.x ให้จับคู่กับ PaddleX 3.3.x และ PaddlePaddle 3.2.x เพื่อหลีกเลี่ยง API/dependency mismatch

```sh
python3.11 -m venv .venv
source .venv/bin/activate
pip install .
uvicorn app.main:app --reload
```

### รันด้วย Docker

จาก root ของโปรเจกต์:

```sh
docker build --no-cache --platform linux/amd64 -t pure-ai-ocr .
docker run --platform linux/amd64 --rm -p 8000:8000 \
  -v pure-ai-paddlex-cache:/root/.paddlex pure-ai-ocr
```

### เปิด Swagger และเรียก OCR

เปิด Swagger UI ที่ `http://localhost:8000/docs`, ReDoc ที่ `http://localhost:8000/redoc` หรือ OpenAPI JSON ที่ `http://localhost:8000/openapi.json`. ใน Swagger เลือก `POST /v1/ocr/slip` แล้วส่งรูปใน multipart field ชื่อ `file` (JPEG, PNG หรือ WebP). Swagger แสดง schema, response example และ error codes.

ครั้งแรกที่ส่งภาพ OCR จะดาวน์โหลด model weights. ต้องมี network access และพื้นที่สำหรับ model cache; ครั้งถัดไปจะใช้ไฟล์ที่ cache ไว้.

ถ้า API ตอบ `503 OCR engine is unavailable` ให้ดู stack trace ฝั่ง container:

```sh
docker ps
docker logs --tail 200 <container-id-or-name>
```

ถ้า stack trace ลงท้ายด้วย `ImportError: libGL.so.1` หรือ `ImportError: libgomp.so.1` ให้ rebuild image ล่าสุด ซึ่งติดตั้ง runtime libraries ที่ OpenCV/PaddleX/PaddlePaddle ต้องใช้แล้ว:

```sh
docker build --no-cache --platform linux/amd64 -t pure-ai-ocr .
docker run --platform linux/amd64 --rm -p 8000:8000 \
  -v pure-ai-paddlex-cache:/root/.paddlex pure-ai-ocr
```

หลังแก้โค้ดให้ rebuild image แล้วสร้าง container ใหม่ เพราะ container เดิมยังใช้ image เก่าอยู่:

```sh
docker build --platform linux/amd64 -t pure-ai-ocr .
docker run --platform linux/amd64 --rm -p 8000:8000 \
  -v pure-ai-paddlex-cache:/root/.paddlex pure-ai-ocr
```

ถ้าต้องการเปิด API key ให้ตั้งค่าก่อนเริ่ม server:

```sh
export OCR_API_KEY='ใส่คีย์ของคุณ'
uvicorn app.main:app --reload
```

สำหรับ Docker ส่งค่า environment ตอนรัน:

```sh
docker run --platform linux/amd64 --rm -p 8000:8000 \
  -v pure-ai-paddlex-cache:/root/.paddlex \
  -e OCR_API_KEY='ใส่คีย์ของคุณ' pure-ai-ocr
```

จากนั้นกรอกคีย์ใน header `X-API-Key` ของ Swagger. ค่าเริ่มต้นว่างไม่บังคับ API key และเหมาะสำหรับ local development เท่านั้น; อย่าเปิดบริการสู่เครือข่ายสาธารณะโดยไม่มี authentication และ TLS.

## API response

มี `bank` เป็น `scb`, `krungthai` หรือ `null`; field ใน `fields` ระบุ `value` และ `confidence` แยกกัน ส่วน `rawText` ช่วยตรวจสอบคุณภาพระหว่างพัฒนา จึงห้ามบันทึกลง log หรือส่งกลับผู้ใช้ปลายทางโดยไม่จำเป็น ข้อมูลนี้มีข้อมูลส่วนบุคคลได้

ไม่ระบุธนาคารที่ไม่อยู่ใน scope, อ่านไม่ชัด หรือจับยอดไม่ได้ จะไม่พยายามเดาค่า และผลยังต้องตรวจทานเสมอ บริการนี้ยังไม่พร้อมเชื่อม production จนกว่าจะมี benchmark จากภาพสลิป SCB/กรุงไทยที่ได้รับอนุญาต

## ระยะถัดไป

1. เก็บชุดตัวอย่าง SCB และกรุงไทยที่มีสิทธิ์ใช้ พร้อม label ที่ double-review
2. วัด field exact match และ character error แยกตามธนาคาร/field แล้วปรับ parser จากข้อผิดพลาดจริง
3. เพิ่ม test corpus ที่ลบข้อมูลระบุตัวบุคคลสำหรับ regression ก่อนต่อเข้ากับ `manager-cost`
4. ทำ shadow mode และ feature flag ใน `manager-cost` หลังคุณภาพผ่านเกณฑ์ที่ตกลงกัน

## แหล่งอ้างอิงโมเดล

PaddleOCR ระบุ PP-OCRv5 รองรับการรู้จำภาษาไทย และยกตัวอย่างการเรียกผ่าน Python API ใน [เอกสารทางการ](https://www.paddleocr.ai/main/en/version3.x/algorithm/PP-OCRv5/PP-OCRv5_multi_languages.html) การรองรับภาษาไม่ได้รับประกันความแม่นยำกับสลิป SCB/กรุงไทย จึงต้องประเมินด้วยชุดข้อมูลของเราเอง
