# แผนโครงการ: OCR ของเราเองสำหรับเอกสารการเงินภาษาไทย

สถานะ: เริ่มทำ MVP ใน `pure-ai` แล้ว — ยังไม่มีการเชื่อมต่อหรือเปลี่ยน `manager-cost`

## Baseline ต้นทุน provider (ประมาณการ ณ 2026-09-26)

โค้ด `manager-cost` เลือก `gemini-2.5-flash-lite` ก่อน และจะลองรุ่นอื่นเมื่อได้ HTTP 429; ราคา API ขึ้นกับ token ที่ใช้จริง ไม่ได้คิดอัตราคงที่ต่อรูป Google ระบุ paid tier ของ Flash-Lite ที่ USD 0.10/1M input tokens และ USD 0.40/1M output tokens; ส่วน Flash fallback ที่ USD 0.30/1M input และ USD 2.50/1M output tokens ([ราคา Gemini API ทางการ](https://ai.google.dev/gemini-api/docs/pricing)).

สำหรับวางแผนเบื้องต้น สมมติ 2,500 input tokens/รูป (prompt/schema + รูปที่ย่อแล้ว) และ 200 output tokens/รูป พร้อมใช้อัตราแลกเปลี่ยนสมมติ 36 บาท/USD:

| กรณี | โดยประมาณ/รูป | 1,000 รูป/เดือน | 10,000 รูป/เดือน | 100,000 รูป/เดือน |
| --- | ---: | ---: | ---: | ---: |
| Flash-Lite เป็นรุ่นที่สำเร็จ | ฿0.01 | ฿10 | ฿100 | ฿1,000 |
| Flash fallback สำหรับทุกภาพ (ประมาณการสูง) | ฿0.05 | ฿50 | ฿500 | ฿5,000 |

ตัวเลขนี้เป็น **estimate ของ paid tier ไม่ใช่ใบแจ้งหนี้จริง**; Free tier อาจทำให้ยอดเรียกเก็บเป็นศูนย์ตามสิทธิ์และ quota ของ project. จำนวน input tokens ของรูปเปลี่ยนตามความละเอียดและการ tile, prompt/output เปลี่ยนได้ และ fallback ไม่เกิดกับทุกภาพ จึงควรใช้ `usageMetadata` กับรุ่นที่สำเร็จและ Google Cloud billing export มาวัดค่าเฉลี่ยจริงแยกตามรุ่น ก่อนล็อก baseline.

**ปริมาณจริงของ MoneyFlow ยังไม่ทราบ:** โค้ดที่ตรวจพบไม่ได้บันทึก counter ภาพ/เดือนหรือ token usage ที่ใช้สรุป volume ได้ แผนจึงใช้ 1k/10k/100k รูปเป็น scenario เท่านั้น ห้ามอ้างเป็น usage production. ระยะ 0 ต้องนับจำนวน OCR attempts และภาพไม่ซ้ำใน `SlipUpload` ต่อเดือนอย่างน้อย 1–3 เดือน แล้วเทียบกับ billing export.

เปรียบเทียบ self-host ด้วยต้นทุนรวมต่อเดือน: VM/GPU หรือ CPU ที่เปิดทิ้งไว้ + storage/egress + monitoring/logging + backup + เวลาคนดูแล/แก้ปัญหา + ค่า retrain/benchmark. จุดคุ้มทุนโดยประมาณคือ `ค่าใช้จ่ายคงที่ self-host ต่อเดือน ÷ (provider บาท/รูป − self-host variable บาท/รูป)`. ถ้าส่วนต่างในวงเล็บไม่เป็นบวกหรือ volume จริงต่ำกว่าจุดคุ้มทุน ให้คง provider หรือใช้ hybrid แทนการย้ายทั้งหมด.

## เป้าหมาย

สร้างบริการ OCR ที่เราควบคุม pipeline, ข้อมูล, การประเมินผล และการ deploy เอง เพื่อนำไปใช้แทน OCR ที่เรียกโมเดลผ่าน provider ใน `manager-cost` ได้เมื่อผ่านเกณฑ์คุณภาพและต้นทุน

คำว่า “ทำ OCR เอง” ในแผนนี้หมายถึงเริ่มจากโมเดลแบบเปิดที่รันบน infrastructure ของเรา แล้วปรับแต่งด้วยข้อมูลเอกสารจริงที่ได้รับอนุญาต ไม่เริ่ม train foundation model จากศูนย์ เพราะต้นทุนข้อมูลและ compute สูงเกินความจำเป็นในระยะแรก

ความคืบหน้าเริ่มต้น: มี FastAPI service, upload validation, OCR engine adapter ที่ใช้ PaddleOCR PP-OCRv5 ภาษาไทย, parser เบื้องต้น และ Dockerfile ใน `pure-ai`; ยังต้อง benchmark กับภาพ SCB/กรุงไทยที่ได้รับอนุญาตก่อนประเมินความแม่นยำหรือเชื่อมระบบจริง

## สิ่งที่พบในระบบปัจจุบัน

- `manager-cost` เป็น monorepo TypeScript: React/Vite, NestJS, MongoDB และ Firebase Storage
- `SlipsService` เก็บรูปก่อน จากนั้นส่งภาพให้ `GeminiService`; ถ้า OCR ล้มเหลวจะบันทึกสถานะและให้ผู้ใช้กรอกเอง
- Gemini คืน JSON สำหรับสลิปโอนเงิน, statement/ใบเสร็จบัตรเครดิต และ cash advance เช่น จำนวนเงิน วันที่ ธนาคาร เลขอ้างอิง และ confidence
- ผล OCR เป็นข้อมูลร่างให้ผู้ใช้ตรวจและยืนยันก่อนสร้าง transaction
- โมเดล/การเรียกปัจจุบันมีการไล่ลองหลายรุ่นเมื่อได้ 429; แผนใหม่ควรรักษา fallback และ manual entry ไว้

## ขอบเขต MVP

1. เอกสารเป้าหมาย: สลิปโอนเงินของธนาคารไทยพาณิชย์ (SCB) และธนาคารกรุงไทย (Krungthai) เท่านั้นใน MVP; ยังไม่รวมธนาคารอื่น ใบเสร็จ หรือ statement บัตรเครดิต
2. รับภาพจากระบบเดิมและส่งกลับผลลัพธ์ใน schema ที่ `manager-cost` ใช้อยู่ โดยไม่เปลี่ยน flow ยืนยันรายการในระยะแรก
3. แยกงานเป็น image preprocessing, text detection/recognition, field extraction และ validation
4. ให้บริการผ่าน API ภายในที่ versioned; เก็บ model version, processing time และผลการประเมิน โดยไม่ log ภาพหรือข้อมูลการเงินดิบ
5. รองรับ human review: ช่องที่อ่านไม่มั่นใจต้องคืน null/สถานะตรวจสอบ ห้ามเดาค่า และ OCR failure ต้องไม่ทำให้การบันทึกข้อมูลด้วยมือใช้ไม่ได้

## แนวทางทางเทคนิคที่ต้องพิสูจน์ก่อนเลือก

- **OCR engine**: ทดลองโมเดล OCR แบบเปิดที่รองรับภาษาไทยและรัน self-hosted เทียบทั้ง detection และ recognition; เริ่มจาก pretrained model ก่อน fine-tune
- **อ่านเอกสารทั้งภาพหรือ OCR แล้ว parse**: เปรียบเทียบ vision-language/document model กับ pipeline OCR + กฎ/โมเดลดึง field แยก เพื่อดูความแม่นยำ ความเร็ว และต้นทุนจริง
- **ดึงข้อมูลมีโครงสร้าง**: ใช้ parser ที่อาศัย text, ตำแหน่ง, รูปแบบเฉพาะธนาคาร และ validation; จำกัดผลให้ตรง JSON schema ปัจจุบัน
- **ให้บริการ**: แยก inference service ออกจาก NestJS เพื่อเลือก runtime/ภาษาและ scaling ได้ โดย NestJS เรียกผ่าน HTTP ภายใน; ใช้ queue เมื่อโหลดหรือ latency ต้องการ
- **ฝึก/ปรับแต่ง**: ทำเมื่อ baseline พิสูจน์แล้วว่าจุดผิดพลาดแก้ด้วย preprocessing หรือ parser ไม่ได้ และมีชุดข้อมูลที่ได้รับอนุญาตเพียงพอ

ยังไม่ล็อกชื่อ framework, รุ่นโมเดล, cloud หรือ GPU จนกว่าจะทำ benchmark บนชุดข้อมูลของเราที่ไม่ปะปนกับ training set

## แผนดำเนินงานและจุดตัดสินใจ

### ระยะ 0 — นิยามงานและ baseline (กำลังดำเนินการ)

- รวบรวมสลิป SCB และกรุงไทยหลายรูปแบบ, ปริมาณต่อวัน, latency ที่ยอมรับได้ และค่าใช้จ่าย provider ปัจจุบัน
- ตกลง schema, ความหมายของ field, การจัดการ พ.ศ., จำนวนเงิน/สกุลเงิน, วันเวลา และกรณีที่ field ไม่มีในเอกสาร
- จัดทำชุด benchmark แบบแยกตามธนาคาร/สภาพภาพ พร้อม ground truth ที่ผู้ตรวจทานยืนยัน
- วัดระบบปัจจุบันเป็น baseline: field accuracy, exact match ของจำนวนเงิน/วัน/เลขอ้างอิง, อัตราต้องแก้มือ, latency, token usage/รุ่นที่สำเร็จ, จำนวนภาพจริงต่อเดือน และค่าใช้จ่ายต่อภาพจาก billing export
- แทน estimate ในส่วน Baseline ต้นทุน provider ด้วยจำนวนภาพและค่าใช้จ่ายจริง 1–3 เดือน; แยก free-tier, paid-tier และ fallback models ให้ชัด
- **จุดตัดสินใจ:** ยืนยันว่า use case แรกคือสลิปโอนเงิน และกำหนดเกณฑ์ผ่านก่อนเริ่มพัฒนา

### ระยะ 1 — ข้อมูลและความเป็นส่วนตัว (ยังต้องทำก่อน benchmark จริง)

- ตรวจสิทธิ์ในการใช้ภาพเดิม; หากไม่มีฐานการอนุญาตชัดเจน ให้เริ่มจากข้อมูลที่ผู้ใช้ยินยอมและปกปิดข้อมูลส่วนบุคคล
- กำหนด retention, encryption, access control, audit trail และกระบวนการลบข้อมูล
- สร้าง annotation guide, เครื่องมือ label และ double review สำหรับค่าความจริงที่สำคัญ
- แบ่ง train/validation/test โดยแยกตามเอกสาร/ผู้ใช้ ไม่ให้ภาพซ้ำหรือเอกสารเดียวกันข้ามชุด
- **จุดตัดสินใจ:** มีข้อมูลคุณภาพและปริมาณเพียงพอสำหรับ benchmark และการปรับแต่งหรือไม่

### ระยะ 2 — Prototype และ benchmark

- ทดลอง preprocessing: หมุนภาพ, crop, ปรับ contrast/ความคมชัด และตรวจคุณภาพภาพ
- เปรียบเทียบ OCR candidates กับสลิป SCB และกรุงไทย รวมภาษาไทย/อังกฤษ ตัวเลขเล็ก ภาพเบลอ แสงสะท้อน และความแตกต่างของ layout ภายในแต่ละธนาคาร
- สร้าง field parser, normalization และ validation (เช่น วันจริง, ยอดเงิน, เลขอ้างอิง) โดยให้ค่าความเชื่อมั่นระดับ field
- ทำ error analysis แยกตามชนิดเอกสาร/ธนาคาร/field แล้วเลือกแนวทางที่คุ้มที่สุด
- **จุดตัดสินใจ:** ผ่านเกณฑ์คุณภาพและต้นทุนหรือไม่; ถ้าไม่ผ่าน ให้ปรับข้อมูล/แนวทางก่อนเพิ่ม scope

### ระยะ 3 — บริการสำหรับทดสอบกับระบบเดิม

- สร้าง inference API แบบ versioned พร้อม auth ภายใน, ขนาดไฟล์สูงสุด, MIME/content validation, timeout, rate limit และ health check
- ทำ response adapter ให้ตรง schema เดิม และคืนสถานะ `needs_review`/manual-entry อย่างชัดเจน
- เพิ่ม metrics แบบไม่บันทึกข้อมูลดิบ: จำนวนงาน, latency, error rate, field confidence และ model version
- เพิ่ม queue/retry เฉพาะข้อผิดพลาดชั่วคราว และ idempotency สำหรับการส่งซ้ำ
- deploy ในสภาพแวดล้อมแยก พร้อมกำหนด resource/GPU และแผน scale ตาม benchmark

### ระยะ 4 — Shadow mode และ pilot

- เชื่อม `manager-cost` แบบ feature flag ให้ OCR เดิมเป็นผลที่ผู้ใช้เห็น ขณะที่บริการใหม่ประมวลผลคู่ขนานโดยไม่กระทบผู้ใช้
- เปรียบเทียบผลใหม่กับผลเดิมและ ground truth ที่มีการตรวจยืนยัน; สุ่มตรวจกรณีที่ระบบเห็นตรงกันด้วย
- เปิดใช้กลุ่มเล็กเมื่อเกณฑ์ผ่าน และเก็บ feedback การแก้ field จากผู้ใช้โดยขอความยินยอม
- คง fallback ไป manual entry และวิธีคืนกลับไป provider เดิมตลอด pilot
- **จุดตัดสินใจ:** ขยายการใช้งานเมื่อคุณภาพ, latency, reliability และต้นทุนจริงผ่านเกณฑ์ต่อเนื่อง

### ระยะ 5 — ปรับปรุงและลดการพึ่ง provider

- ใช้ข้อผิดพลาดที่ตรวจทานแล้วเพิ่มชุดฝึกและ fine-tune เฉพาะเมื่อมีประโยชน์วัดได้
- ติดตาม data/model drift และ regression ทุกครั้งที่เปลี่ยน model หรือ parser
- ลดสัดส่วน provider ทีละขั้น และวางแผน decommission หลังผ่านช่วงเสถียรภาพที่ตกลงกัน

## เกณฑ์ยอมรับที่ต้องตกลงก่อนเริ่ม

กำหนดตัวเลขจาก baseline และความเสี่ยงทางบัญชี ไม่ตั้งตัวเลขลอย ๆ โดยอย่างน้อยต้องวัด:

- exact match ของยอดเงิน, วันเวลา, ธนาคาร และเลขอ้างอิง แยกตาม field และธนาคาร
- อัตราที่ผู้ใช้ต้องแก้ข้อมูล และอัตราที่ต้องกรอกใหม่ทั้งหมด
- false extraction ของข้อมูลสำคัญ และสัดส่วนผลที่ถูกส่งให้ผู้ใช้ตรวจ
- p50/p95 latency, uptime/error rate และต้นทุนต่อภาพรวมค่า compute/จัดเก็บ/ดูแลระบบ
- ไม่มีการนำผล confidence ต่ำไปสร้าง transaction โดยไม่ผ่านการตรวจยืนยันของผู้ใช้

## ความเสี่ยงและการควบคุม

- **อ่านยอด/วันที่ผิด:** ทำเป็น draft, validation ข้าม field, confidence ต่อ field และผู้ใช้ยืนยันก่อนบันทึก
- **ข้อมูลฝึกมีสิทธิ์ไม่ชัด:** ห้ามนำภาพ production ไปฝึกจนมีฐานสิทธิ์, consent และ retention ที่อนุมัติ
- **ข้อมูลส่วนบุคคลรั่วใน log:** ปิด raw image/text logging, จำกัดสิทธิ์ และกำหนดอายุข้อมูล
- **ความหลากหลายของ layout:** เก็บ benchmark แยกธนาคารและติดตาม drift; เริ่มรองรับขอบเขตแคบก่อน
- **ดูแลโมเดลเองมีต้นทุนสูง:** ใช้ต้นทุนรวม (เครื่อง, GPU/CPU ที่ idle, storage, egress, monitoring, on-call, retraining และเวลาวิศวกร) กับ volume จริงคำนวณ break-even เทียบ provider ก่อนตัดสินใจแทนจริง
- **ผลใหม่ไม่เข้ากับระบบเดิม:** ทำ adapter และ versioned contract; ใช้ feature flag, shadow mode และ rollback

## สิ่งที่ยังต้องตอบก่อนเริ่มระยะ 0

1. “OCR ของเราเอง” หมายถึง self-host โมเดลสำเร็จรูป/ปรับแต่งโมเดล หรือจำเป็นต้อง train model เองตั้งแต่ต้น?
2. มีภาพสลิป SCB และกรุงไทยที่ได้รับอนุญาตให้ใช้ทำ benchmark/ฝึกกี่ภาพ และข้อมูลชุดนี้จะเก็บใน environment ใด?
3. ปริมาณภาพต่อเดือน, latency เป้าหมาย, งบ infrastructure และเกณฑ์แม่นยำขั้นต่ำคือเท่าไร?
4. ต้องการ deploy บน cloud/provider เดิม หรือมีข้อกำหนด on-premise/region/data residency?

## สิ่งที่ยังไม่รวม

- ยังไม่เปลี่ยน endpoint หรือ flow ใน `manager-cost`
- ยังไม่เลือกหรือดาวน์โหลด model, สร้าง dataset, train, deploy หรือเปิดใช้งานกับผู้ใช้
- ยังไม่รองรับธนาคารอื่นหรือเอกสารทุกประเภท; MVP จำกัดที่สลิป SCB และกรุงไทย และจะขยายขอบเขตเมื่อมี benchmark รองรับ
