# TikTok Live Auto Typer for Word Guessing Game

โปรแกรมสำหรับรับคอมเมนต์จาก TikTok Live และพิมพ์ลงในเกมเดาคำอัตโนมัติ

## ฟีเจอร์หลัก

- **รับคอมเมนต์จาก TikTok Live** แบบ real-time
- **พิมพ์อัตโนมัติ** ลงในเว็บเกมผ่าน Selenium
- **ระบบกรองข้อความ** หลากหลาย (prefix, blacklist, group filter, duplicate, max length)
- **Auto Start/Stop** เมื่อเกมเริ่ม/จบ
- **ตรวจสอบ input field** อัตโนมัติ
- **ไม่ต้องให้เมาส์อยู่ที่จอ** ตลอดเวลา

## การติดตั้ง

1. ติดตั้ง Python 3.7+
2. ติดตั้ง dependencies:
```bash
pip install -r requirements.txt
```

3. ดาวน์โหลด ChromeDriver และใส่ใน PATH หรือโฟลเดอร์เดียวกับโปรแกรม

## การใช้งาน

1. **เปิดโปรแกรม**:
```bash
python main_selenium.py
```

2. **ตั้งค่า**:
   - ใส่ TikTok Unique ID ของสตรีมเมอร์
   - ใส่ URL ของเว็บเกม
   - เปิดเว็บเกมด้วยปุ่ม "Open Web"

3. **เริ่มเล่น**:
   - กด "Start Listener" เพื่อเริ่มรับคอมเมนต์
   - รอให้เกมโหลดเสร็จ (จะแสดง "Web Ready: Input field found")
   - กด "Start Typing" เพื่อเริ่มพิมพ์อัตโนมัติ

4. **การควบคุม**:
   - ปุ่ม "Stop Typing" หยุดการพิมพ์
   - ปุ่ม "Close Web" ปิดเว็บและหยุดการทำงาน
   - ระบบจะหยุดอัตโนมัติเมื่อเกมจบ

## ระบบกรองข้อความ

- **Prefix Filter**: กรองข้อความที่ขึ้นต้นด้วยคำเฉพาะ
- **Blacklist Filter**: กรองคำที่ไม่อยากให้พิมพ์
- **Group Filter**: กรองตามภาษา (ไทย/อังกฤษ/ตัวเลข/สัญลักษณ์)
- **Duplicate Filter**: ป้องกันการพิมพ์ข้อความซ้ำ
- **Max Length Filter**: จำกัดความยาวข้อความ

## หมายเหตุ

- ต้องมี ChromeDriver ที่เข้ากันได้กับ Chrome version ที่ติดตั้ง
- ระบบจะตรวจสอบ input field ทุก 2 วินาที
- เมื่อเกมจบ ระบบจะหยุดการพิมพ์อัตโนมัติ