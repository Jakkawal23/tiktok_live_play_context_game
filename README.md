# TikTok Live → Game Input Bot

โปรเจกต์นี้ใช้สำหรับดึงข้อความจาก TikTok Live Chat แล้วส่งข้อความไปยังเกมบนเว็บ  
(สามารถเลือกได้ว่าจะพิมพ์อัตโนมัติด้วย `pyautogui` หรือควบคุม browser ด้วย `selenium`)

---

# วิธีติดตั้งและใช้งาน

## Windows (PowerShell)

### 1. สร้าง Virtual Environment
```bash
python -m venv venv
```

### 2. เข้า Virtual Environment
```bash
.\venv\Scripts\activate
```

### 3. ติดตั้ง dependencies
```bash
pip install -r requirements.txt
```

### 4. รันโปรแกรม
```bash
python main.py
```

## macOS / Linux

### 1. สร้าง Virtual Environment
```bash
python3 -m venv venv
```

### 2. เข้า Virtual Environment
```bash
source venv/bin/activate
```

### 3. ติดตั้ง dependencies
```bash
pip install -r requirements.txt
```

### 4. รันโปรแกรม
```bash
python main.py  
```