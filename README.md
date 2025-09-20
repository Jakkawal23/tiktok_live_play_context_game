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

### 4. รันโปรแกรม Connect to live
```bash
python main.py
```

### รันด้วย pyautogui
```bash
python main_pyautogui.py
```

### รันด้วย pyautogui แสดง gui
```bash
python main_pyautogui_gui.py
```

### รันด้วย selenium
```bash
python main_selenium.py
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

### 4. รันโปรแกรม Connect to live
```bash
python main.py
```

### รันด้วย pyautogui
```bash
python main_pyautogui.py
```

### รันด้วย pyautogui แสดง gui
```bash
python main_pyautogui_gui.py
```

### รันด้วย selenium
```bash
python main_selenium.py
```

## ทำเป็นไฟล์ exe

### 1. ติดตั้ง PyInstaller
```bash
pip install pyinstaller
```

### ตรวจสอบว่า install สำเร็จ
```bash
pyinstaller --version
```

### 2. สร้าง .exe (เข้าไปโฟลเดอร์โปรเจกต์)
```bash
pyinstaller --onefile --windowed --name "TikTokAutoTyper" --icon="C:\path\to\icon.ico" main_pyautogui_gui.py
```
- `--onefile` → รวมทุกอย่างเป็นไฟล์เดียว
- `--windowed` → ไม่เปิด console (เหมาะกับ GUI)
- `--name` → ตั้งชื่อไฟล์ .exe
- `--icon` → ใส่ไอคอน


### ถ้าต้องการไอคอน
```bash
pyinstaller --onefile --windowed --icon=app_icon.ico main_pyautogui_gui.py
```

