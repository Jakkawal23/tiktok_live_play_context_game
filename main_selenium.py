import sys
import re
import queue
import threading
import time
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QPushButton,
    QTextEdit, QVBoxLayout, QHBoxLayout, QCheckBox, QSpinBox
)
from PyQt5.QtCore import QTimer, pyqtSignal , Qt
from PyQt5.QtGui import QFont, QIcon
from TikTokLive import TikTokLiveClient
from TikTokLive.events import CommentEvent, ConnectEvent, DisconnectEvent
from pynput.keyboard import Controller, Key
import random
import asyncio

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import NoSuchElementException

# ----------------------
# ฟังก์ชันช่วยเหลือ
# ----------------------
def clean_text(text):
    """
    ลบ emoji และสัญลักษณ์บางชนิดออกจากข้อความ
    เพื่อให้ข้อความปลอดภัยสำหรับการพิมพ์
    """
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # Emoticons
        "\U0001F300-\U0001F5FF"  # Symbols & Pictographs
        "\U0001F680-\U0001F6FF"  # Transport & Map Symbols
        "\U0001F1E0-\U0001F1FF"  # Flags
        "\U00002700-\U000027BF"  # Dingbats
        "\U0001F900-\U0001F9FF"  # Supplemental Symbols & Pictographs
        "\U00002600-\U000026FF"  # Misc symbols
        "\U00002B00-\U00002BFF"  # Arrows, etc.
        "]+",
        flags=re.UNICODE
    )
    text = emoji_pattern.sub("", text)
    return text

def filter_by_group(text, gui):
    """
    กรองข้อความตามกลุ่มที่เลือกใน GUI
    - Thai
    - English
    - Number
    - Special character
    """
    result = ""
    for c in text:
        if "\u0E00" <= c <= "\u0E7F":  # Thai
            if gui.group_thai_checkbox.isChecked():
                result += c
        elif "A" <= c <= "Z" or "a" <= c <= "z":  # English
            if gui.group_english_checkbox.isChecked():
                result += c
        elif c.isdigit():  # Number
            if gui.group_number_checkbox.isChecked():
                result += c
        else:  # Special characters
            if gui.group_special_checkbox.isChecked():
                result += c
    return result


def apply_blacklist(text, blacklist_str):
    """
    กรองข้อความตาม blacklist (อักขระ/คำที่ห้าม)
    """
    if not blacklist_str:
        return text

    blacklist = [re.escape(w.strip()) for w in blacklist_str.split(",") if w.strip()]
    if not blacklist:
        return text

    # สร้าง regex pattern และแทนที่ด้วย empty string
    pattern = "[" + "".join(blacklist) + "]"
    return re.sub(pattern, "", text)

# ----------------------
# Typing Thread
# ----------------------
class TypingThread(threading.Thread):
    """
    Thread สำหรับพิมพ์ข้อความจาก Queue ออกไป
    """
    def __init__(self, comment_queue):
        super().__init__()
        self.comment_queue = comment_queue
        self.keyboard = Controller()  # ใช้ pynput keyboard
        self.running = False
        self.prefix_enabled = False
        self.prefix_str = ""

    def start_typing(self, prefix_enabled=False, prefix_str=""):
        """
        เริ่มต้นการพิมพ์ข้อความ
        """
        self.prefix_enabled = prefix_enabled
        self.prefix_str = prefix_str
        self.running = True

    def stop_typing(self):
        """
        หยุดการพิมพ์
        """
        self.running = False

    def run(self):
        while True:
            if self.running and not self.comment_queue.empty():
                # ตรวจสอบ input field ก่อน get ข้อความ
                if hasattr(self, "gui") and self.gui.input_field_found:
                    text = self.comment_queue.get()
                    # Apply clean_text ทุกกรณี
                    text_to_type = clean_text(text)
                    # Apply prefix เฉพาะเมื่อเลือก checkbox
                    if getattr(self, "prefix_enabled", False) and self.prefix_str:
                        text_to_type = f"{self.prefix_str}{text_to_type}"
                    # ตรวจสอบว่าเป็น admin message หรือไม่
                    is_admin_message = text.startswith("🔧 ADMIN:")
                    if is_admin_message:
                        text_to_type = text.replace("🔧 ADMIN:", "").strip()
                    # Apply group filter เฉพาะเมื่อเลือก checkbox
                    if hasattr(self, "gui") and (
                        self.gui.group_thai_checkbox.isChecked() or
                        self.gui.group_english_checkbox.isChecked() or
                        self.gui.group_number_checkbox.isChecked() or
                        self.gui.group_special_checkbox.isChecked()
                    ):
                        text_to_type = filter_by_group(text_to_type, self.gui)
                    # Apply blacklist เฉพาะเมื่อเลือก checkbox
                    if getattr(self, "blacklist_enabled", False) and getattr(self, "blacklist_str", ""):
                        text_to_type = apply_blacklist(text_to_type, self.blacklist_str)
                    # Remove space เฉพาะเมื่อเลือก checkbox
                    if getattr(self, "remove_space_enabled", False):
                        text_to_type = text_to_type.replace(" ", "")
                    try:
                        selector = self.gui.entry_selector.text().strip() or 'input[name="word"]'
                        input_element = self.gui.driver.find_element(By.CSS_SELECTOR, selector)
                        if not input_element.is_displayed():
                            print("Input field not displayed")
                            self.gui.input_field_fail_count += 1
                            if self.gui.input_field_fail_count >= 3:
                                self.gui.stop_typing_signal.emit()
                            # put text back to queue
                            self.comment_queue.put(text)
                            time.sleep(0.5)
                            continue
                        if not input_element.is_enabled():
                            print("Input field not enabled")
                            self.gui.input_field_fail_count += 1
                            if self.gui.input_field_fail_count >= 3:
                                self.gui.stop_typing_signal.emit()
                            # put text back to queue
                            self.comment_queue.put(text)
                            time.sleep(0.5)
                            continue
                        # ...existing code for clickability check...
                        self.gui.input_field_fail_count = 0
                        is_readonly = input_element.get_attribute("readonly")
                        is_disabled = input_element.get_attribute("disabled")
                        if is_readonly or is_disabled:
                            print("Input field is readonly or disabled, waiting...")
                            # put text back to queue
                            self.comment_queue.put(text)
                            time.sleep(0.5)
                            continue
                        current_value = input_element.get_attribute("value")
                        if current_value and current_value.strip():
                            print(f"Clearing old value in input field: '{current_value}'")
                            input_element.clear()
                            time.sleep(0.1)
                            remaining_value = input_element.get_attribute("value")
                            if remaining_value and remaining_value.strip():
                                print(f"Still has value after clear: '{remaining_value}', using Ctrl+A+Delete")
                                input_element.send_keys(Keys.CONTROL + "a")
                                input_element.send_keys(Keys.DELETE)
                                time.sleep(0.1)
                                final_value = input_element.get_attribute("value")
                                if final_value and final_value.strip():
                                    print(f"Still has value after Ctrl+A+Delete: '{final_value}', trying backspace")
                                    for _ in range(len(final_value) + 5):
                                        input_element.send_keys(Keys.BACKSPACE)
                                    time.sleep(0.1)
                        final_check = input_element.get_attribute("value")
                        if final_check and final_check.strip():
                            print(f"Input field still has value: '{final_check}', skipping this input")
                            # put text back to queue
                            self.comment_queue.put(text)
                            time.sleep(0.5)
                            continue
                        if getattr(self, "pre_delay_enabled", False):
                            time.sleep(getattr(self, "pre_delay_ms", 0) / 1000.0)
                        print(f"Typing new value: '{text_to_type}'")
                        queue_size = self.comment_queue.qsize()
                        if queue_size > 10:
                            char_delay = random.uniform(0.005, 0.015)
                            enter_delay = random.uniform(0.05, 0.1)
                        elif queue_size > 5:
                            char_delay = random.uniform(0.01, 0.025)
                            enter_delay = random.uniform(0.08, 0.15)
                        else:
                            char_delay = random.uniform(0.015, 0.035)
                            enter_delay = random.uniform(0.1, 0.2)
                        for char in text_to_type:
                            input_element.send_keys(char)
                            time.sleep(char_delay)
                        time.sleep(enter_delay)
                        try:
                            input_element.send_keys("\n")
                        except:
                            try:
                                input_element.send_keys(Keys.RETURN)
                            except:
                                pass
                        if getattr(self, "post_delay_enabled", False):
                            time.sleep(getattr(self, "post_delay_ms", 0) / 1000.0)
                        # Discard pending_messages เฉพาะเมื่อเปิด duplicate filter
                        if hasattr(self, "gui") and hasattr(self.gui.listener_thread, "duplicate_enabled"):
                            if self.gui.listener_thread.duplicate_enabled:
                                if text in self.gui.listener_thread.pending_messages:
                                    self.gui.listener_thread.pending_messages.discard(text)
                    except Exception as e:
                        self.gui.input_field_fail_count += 1
                        print(f"Input field error (attempt {self.gui.input_field_fail_count}): {e}")
                        if self.gui.input_field_fail_count >= 5:
                            print("Input field not available after 5 attempts, stopping typing...")
                            self.gui.stop_typing_signal.emit()
                        # put text back to queue
                        self.comment_queue.put(text)
                        time.sleep(0.5)
                        continue
                else:
                    # input field ยังไม่เจอ ให้รอ ไม่ต้อง get ข้อความออกจาก queue
                    time.sleep(0.2)
            else:
                time.sleep(0.1)

# ----------------------
# TikTok Listener Thread
# ----------------------
class TikTokListener(threading.Thread):
    """
    Thread สำหรับฟัง comment จาก TikTok Live
    """
    def __init__(self, unique_id, gui_callback, typing_queue, status_callback):
        super().__init__()
        self.client = TikTokLiveClient(unique_id=unique_id)
        self.gui_callback = gui_callback  # callback แสดงใน GUI
        self.typing_queue = typing_queue  # Queue ส่งต่อให้ TypingThread
        self.status_callback = status_callback  # อัพเดตสถานะ GUI
        self.loop = None
        self.running = False
        self.task = None

        # เก็บข้อความที่อยู่ใน queue / กำลังพิมพ์ สำหรับ duplicate filter
        self.pending_messages = set()
        
        # ตัวนับการตรวจสอบ input field ที่ล้มเหลว
        self.input_field_fail_count = 0

        # -------------------
        # Event callback จาก TikTokLiveClient
        # -------------------
        @self.client.on(CommentEvent)
        async def on_comment(event: CommentEvent):
            text = event.comment.strip()
            if not text:
                return

            # แสดงในช่องแชททุกครั้ง
            self.gui_callback(event.user.nickname, text)

            # เฉพาะตอนที่กำลังพิมพ์ถึงจะใส่เข้า queue
            if hasattr(self, 'typing_thread') and getattr(self.typing_thread, 'running', False):
                maxlen_enabled = getattr(self, 'maxlen_enabled', False)
                maxlen = getattr(self, 'maxlen_value', 2000)
                if maxlen_enabled and len(text) > maxlen:
                    return

                duplicate_enabled = getattr(self, 'duplicate_enabled', False)
                if duplicate_enabled:
                    if text in self.pending_messages:
                        print(f"Duplicate message filtered: '{text}'")
                        return
                    self.pending_messages.add(text)

                if self.typing_queue is not None:
                    self.typing_queue.put(text)
                    if duplicate_enabled:
                        self.pending_messages.add(text)
                    else:
                        print(f"Message added to queue: '{text}'")

        @self.client.on(ConnectEvent)
        async def on_connect(event: ConnectEvent):
            self.status_callback("connected")  # GUI อัพเดตสถานะ

        @self.client.on(DisconnectEvent)
        async def on_disconnect(event: DisconnectEvent):
            self.status_callback("disconnected")  # GUI อัพเดตสถานะ

    def run(self):
        """
        Loop หลักของ Listener Thread
        - สร้าง event loop ของ asyncio
        - run TikTokLiveClient
        """
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.running = True

        try:
            self.task = self.loop.create_task(self.client.run())
            while self.running and not self.task.done():
                self.loop.run_until_complete(asyncio.sleep(0.1))
        except Exception as e:
            self.status_callback("failed")
            print("Listener error:", e)
        finally:
            try:
                self.loop.run_until_complete(self.client.close())
            except Exception as e:
                print(f"Error closing TikTokLiveClient: {e}")
            self.loop.close()

    def stop(self):
        self.running = False
        if self.loop and not self.loop.is_closed():
            self.loop.call_soon_threadsafe(lambda: self.loop.create_task(self.client.close()))

# ----------------------
# GUI
# ----------------------
class TikTokGUI(QWidget):
    new_comment_signal = pyqtSignal(str, str)  # nickname, text
    stop_typing_signal = pyqtSignal()  # signal สำหรับหยุดการพิมพ์จาก thread อื่น

    def __init__(self):
        super().__init__()
        self.setWindowTitle("TikTok Live Auto Typer")
        self.setWindowIcon(QIcon("program_icon_1.ico"))
        self.comment_queue = queue.Queue()

        # -------------------
        # Threads
        # -------------------
        self.listener_thread = None
        self.typing_thread = TypingThread(self.comment_queue)
        self.typing_thread.daemon = True
        self.typing_thread.start()

        # -------------------
        # GUI Layout
        # -------------------
        layout = QVBoxLayout()

        # ------------------------
        # URL Input + Open/Close Web
        # ------------------------
        h_url = QHBoxLayout()
        h_url.addWidget(QLabel("Game URL:"))
        self.entry_url = QLineEdit()
        self.entry_url.setPlaceholderText("https://...")
        h_url.addWidget(self.entry_url)
        self.btn_open_web = QPushButton("Open Web")
        self.btn_open_web.clicked.connect(self.open_web)
        h_url.addWidget(self.btn_open_web)
        self.btn_close_web = QPushButton("Close Web")
        self.btn_close_web.setStyleSheet("background-color: red; color: white")
        self.btn_close_web.clicked.connect(self.close_web)
        self.btn_close_web.hide()  # ซ่อนไว้ตอนเริ่มต้น
        h_url.addWidget(self.btn_close_web)
        layout.addLayout(h_url)

        # Selenium driver
        self.driver = None
        self.input_field_found = False

        # TikTok Unique ID
        h_uid = QHBoxLayout()
        h_uid.addWidget(QLabel("TikTok Unique ID:"))
        self.entry_uid = QLineEdit()
        h_uid.addWidget(self.entry_uid)
        layout.addLayout(h_uid)


        # Prefix filter
        h_prefix = QHBoxLayout()
        self.prefix_checkbox = QCheckBox("Enable Prefix Filter")
        self.prefix_input = QLineEdit()
        self.prefix_input.setPlaceholderText("Enter prefix (e.g., _ )")
        h_prefix.addWidget(self.prefix_checkbox)
        h_prefix.addWidget(self.prefix_input)
        layout.addLayout(h_prefix)

        # Blacklist filter
        h_blacklist = QHBoxLayout()
        self.blacklist_checkbox = QCheckBox("Enable Blacklist Filter")
        self.blacklist_input = QLineEdit()
        self.blacklist_input.setPlaceholderText("Enter blacklist words/numbers, separated by ,")
        h_blacklist.addWidget(self.blacklist_checkbox)
        h_blacklist.addWidget(self.blacklist_input)
        layout.addLayout(h_blacklist)

        # Pre-typing delay
        h_pre_delay = QHBoxLayout()
        self.pre_delay_checkbox = QCheckBox("Enable Pre-Typing Delay (ms)")
        self.pre_delay_input = QSpinBox()
        self.pre_delay_input.setRange(0, 10000)
        self.pre_delay_input.setValue(0)
        h_pre_delay.addWidget(self.pre_delay_checkbox)
        h_pre_delay.addWidget(self.pre_delay_input)
        layout.addLayout(h_pre_delay)

        # Post-typing delay
        h_post_delay = QHBoxLayout()
        self.post_delay_checkbox = QCheckBox("Enable Post-Typing Delay (ms)")
        self.post_delay_input = QSpinBox()
        self.post_delay_input.setRange(0, 10000)
        self.post_delay_input.setValue(0)
        h_post_delay.addWidget(self.post_delay_checkbox)
        h_post_delay.addWidget(self.post_delay_input)
        layout.addLayout(h_post_delay)

        # Max length filter
        h_maxlen = QHBoxLayout()
        self.maxlen_checkbox = QCheckBox("Enable Max Length Filter")
        self.maxlen_input = QSpinBox()
        self.maxlen_input.setRange(1, 1000)
        self.maxlen_input.setValue(100)
        h_maxlen.addWidget(self.maxlen_checkbox)
        h_maxlen.addWidget(self.maxlen_input)
        layout.addLayout(h_maxlen)

        # Group filters (Thai / English / Number / Special)
        h_group = QHBoxLayout()
        self.group_thai_checkbox = QCheckBox("Thai")
        self.group_english_checkbox = QCheckBox("English")
        self.group_number_checkbox = QCheckBox("Number")
        self.group_special_checkbox = QCheckBox("Special")
        # default all checked
        self.group_thai_checkbox.setChecked(True)
        self.group_english_checkbox.setChecked(True)
        self.group_number_checkbox.setChecked(True)
        self.group_special_checkbox.setChecked(True)

        self.label_group = QLabel("Filter Groups:")
        h_group.addWidget(self.label_group)
        h_group.addWidget(self.group_thai_checkbox)
        h_group.addWidget(self.group_english_checkbox)
        h_group.addWidget(self.group_number_checkbox)
        h_group.addWidget(self.group_special_checkbox)
        layout.addLayout(h_group)

        # Input Field Selector (ใน advance setting)
        h_selector = QHBoxLayout()
        self.selector_label = QLabel("Input Field Selector:")
        self.entry_selector = QLineEdit()
        self.entry_selector.setText('input[name="word"]')  # default value
        self.entry_selector.setPlaceholderText("CSS selector for input field")
        h_selector.addWidget(self.selector_label)
        h_selector.addWidget(self.entry_selector)
        layout.addLayout(h_selector)

        # Duplicate filter
        self.duplicate_checkbox = QCheckBox("Filter duplicate messages in queue")
        layout.addWidget(self.duplicate_checkbox)

        # Remove space option
        self.remove_space_checkbox = QCheckBox("Remove spaces")
        self.remove_space_checkbox.setChecked(False)
        layout.addWidget(self.remove_space_checkbox)

        # Advanced settings button
        h_advance = QHBoxLayout()
        h_advance.addStretch()
        self.btn_advance = QPushButton("Advanced Settings")
        self.btn_advance.setStyleSheet("color: blue; background: transparent; border: none;")
        self.btn_advance.setCursor(Qt.PointingHandCursor)
        self.btn_advance.setCheckable(True)
        self.btn_advance.setChecked(False)
        self.btn_advance.clicked.connect(self.toggle_advanced)
        h_advance.addWidget(self.btn_advance)
        layout.addLayout(h_advance)

        # QTextEdit แสดง comment
        self.text_area = QTextEdit()
        self.text_area.setReadOnly(True)
        layout.addWidget(self.text_area)

        # Custom Message Section
        h_custom = QHBoxLayout()
        self.btn_custom_message = QPushButton("Custom Message")
        self.btn_custom_message.setStyleSheet("color: blue; background: transparent; border: none;")
        self.btn_custom_message.setCursor(Qt.PointingHandCursor)
        self.btn_custom_message.setCheckable(True)
        self.btn_custom_message.setChecked(False)
        self.btn_custom_message.clicked.connect(self.toggle_custom_message)
        h_custom.addWidget(self.btn_custom_message)
        h_custom.addStretch()
        layout.addLayout(h_custom)

        # Custom Message Input (ซ่อนไว้ตอนเริ่มต้น)
        self.custom_message_widget = QWidget()
        custom_layout = QVBoxLayout()
        
        h_custom_input = QHBoxLayout()
        h_custom_input.addWidget(QLabel("Custom Message:"))
        self.entry_custom_message = QLineEdit()
        self.entry_custom_message.setPlaceholderText("Enter your custom message...")
        self.entry_custom_message.returnPressed.connect(self.send_custom_message)  # กด Enter เพื่อส่ง
        h_custom_input.addWidget(self.entry_custom_message)
        
        self.btn_send_custom = QPushButton("Send")
        self.btn_send_custom.setStyleSheet("background-color: #4CAF50; color: white; border-radius: 5px; padding: 5px;")
        self.btn_send_custom.clicked.connect(self.send_custom_message)
        h_custom_input.addWidget(self.btn_send_custom)
        
        custom_layout.addLayout(h_custom_input)
        self.custom_message_widget.setLayout(custom_layout)
        self.custom_message_widget.hide()
        layout.addWidget(self.custom_message_widget)

        # ปุ่ม Start/Stop Listener และ Typing
        h_buttons = QHBoxLayout()
        self.btn_listener = QPushButton("Start Listener")
        self.btn_listener.setStyleSheet("background-color: green; color: white")
        self.btn_listener.clicked.connect(self.toggle_listener)
        h_buttons.addWidget(self.btn_listener)

        self.btn_start_typing = QPushButton("Start Typing")
        self.btn_start_typing.setEnabled(False)
        self.btn_start_typing.clicked.connect(self.start_typing_countdown)
        h_buttons.addWidget(self.btn_start_typing)

        self.btn_stop_typing = QPushButton("Stop Typing")
        self.btn_stop_typing.clicked.connect(self.stop_typing)
        self.btn_stop_typing.hide()
        h_buttons.addWidget(self.btn_stop_typing)


        layout.addLayout(h_buttons)

        # Status labels
        self.status_label_listener = QLabel("Listener: Off")
        self.status_label_typing = QLabel("Typing: Idle")
        layout.addWidget(self.status_label_listener)
        layout.addWidget(self.status_label_typing)

        self.setLayout(layout)

        self.toggle_advanced()  # เริ่มต้นซ่อน advanced settings

        # Signal สำหรับอัพเดต comment ใน GUI
        self.new_comment_signal.connect(self.display_comment)
        self.stop_typing_signal.connect(self.stop_typing)

    def toggle_advanced(self):
        """
        ซ่อน/โชว์ advanced settings
        """
        show = self.btn_advance.isChecked()
        self.prefix_checkbox.setVisible(show)
        self.prefix_input.setVisible(show)
        self.blacklist_checkbox.setVisible(show)
        self.blacklist_input.setVisible(show)
        self.pre_delay_checkbox.setVisible(show)
        self.pre_delay_input.setVisible(show)
        self.post_delay_checkbox.setVisible(show)
        self.post_delay_input.setVisible(show)
        self.maxlen_checkbox.setVisible(show)
        self.maxlen_input.setVisible(show)
        self.duplicate_checkbox.setVisible(show)
        self.remove_space_checkbox.setVisible(show)
        self.label_group.setVisible(show)
        self.group_thai_checkbox.setVisible(show)
        self.group_english_checkbox.setVisible(show)
        self.group_number_checkbox.setVisible(show)
        self.group_special_checkbox.setVisible(show)
        
        # Input Field Selector (ใน advance setting)
        self.selector_label.setVisible(show)
        self.entry_selector.setVisible(show)

    def toggle_custom_message(self):
        """
        ซ่อน/โชว์ custom message input
        """
        show = self.btn_custom_message.isChecked()
        self.custom_message_widget.setVisible(show)
        if show:
            self.btn_custom_message.setText("Custom Message ▼")
        else:
            self.btn_custom_message.setText("Custom Message")

    # ----------------------
    # Display comment (main thread)
    # ----------------------
    def display_comment(self, nickname, text):
        display_text = f"{nickname}: {text}\n"
        
        # เปลี่ยนสีข้อความ live ให้เป็นสีดำ
        cursor = self.text_area.textCursor()
        cursor.movePosition(cursor.End)
        
        # ตั้งค่าสีดำสำหรับข้อความ live
        format = cursor.charFormat()
        format.setForeground(Qt.black)  # สีดำ
        format.setFontWeight(400)  # ปกติ
        cursor.setCharFormat(format)
        
        # แทรกข้อความ
        cursor.insertText(display_text)
        
        # รีเซ็ตรูปแบบ
        format.setForeground(Qt.black)
        format.setFontWeight(400)
        cursor.setCharFormat(format)
        
        self.text_area.verticalScrollBar().setValue(self.text_area.verticalScrollBar().maximum())

    def send_custom_message(self):
        """
        ส่งข้อความ custom ไปยังคิวและแสดงใน chat
        """
        message = self.entry_custom_message.text().strip()
        if not message:
            return

        # แสดงข้อความใน chat พร้อมตกแต่ง
        self.display_admin_message(message)
        
        # เพิ่มข้อความเข้าไปในคิวพร้อม prefix admin
        # Admin message ไม่ผ่าน duplicate filter
        admin_message = f"🔧 ADMIN:{message}"
        self.comment_queue.put(admin_message)
        
        # เคลียร์ input field
        self.entry_custom_message.clear()
        
        print(f"Admin message added to queue: '{message}'")

    def display_admin_message(self, message):
        """
        แสดงข้อความ admin ใน chat พร้อมตกแต่ง
        """
        # สร้างข้อความที่ตกแต่งแล้ว
        admin_text = f"🔧 ADMIN: {message}\n"
        
        # เปลี่ยนสีข้อความ admin
        cursor = self.text_area.textCursor()
        cursor.movePosition(cursor.End)
        
        # ตั้งค่าสีและรูปแบบ
        format = cursor.charFormat()
        format.setForeground(Qt.blue)  # สีน้ำเงิน
        format.setFontWeight(700)  # ตัวหนา
        cursor.setCharFormat(format)
        
        # แทรกข้อความ
        cursor.insertText(admin_text)
        
        # รีเซ็ตรูปแบบ
        format.setForeground(Qt.black)
        format.setFontWeight(400)
        cursor.setCharFormat(format)
        
        # เลื่อนไปด้านล่าง
        self.text_area.verticalScrollBar().setValue(self.text_area.verticalScrollBar().maximum())

    # ----------------------
    # Listener control
    # ----------------------
    def toggle_listener(self):
        """
        Start / Stop listener
        """
        if self.listener_thread is None:
            uid = self.entry_uid.text().strip()
            if not uid:
                return

            # เคลียร์หน้าจอทุกครั้งก่อนเริ่ม
            self.text_area.clear()
            
            # เคลียร์ queue เก่า
            while not self.comment_queue.empty():
                self.comment_queue.get()

            # สร้าง listener
            self.listener_thread = TikTokListener(
                uid,
                self.new_comment_signal.emit,
                self.comment_queue,
                self.update_listener_status
            )
            self.listener_thread.typing_thread = self.typing_thread  # สำคัญ!
            self.listener_thread.daemon = True
            self.listener_thread.start()

            self.btn_listener.setText("Stop Listener")
            self.btn_listener.setStyleSheet("background-color: red; color: white")
            self.status_label_listener.setText("Listener: Connecting...")
            self.btn_start_typing.setEnabled(False)
        else:
            # กด Stop Listener - หยุดแค่รับข้อความจาก live แต่ยังคงส่งผ่าน admin ได้
            if self.listener_thread:
                # หยุดการแสดงข้อความใน GUI
                self.listener_thread.gui_callback = lambda n,t: None
                # หยุดการส่งข้อความเข้า queue
                self.listener_thread.typing_queue = None
                self.listener_thread.stop()
                self.listener_thread.join(timeout=2)
                self.listener_thread = None

            self.btn_listener.setText("Start Listener")
            self.btn_listener.setStyleSheet("background-color: green; color: white")
            self.status_label_listener.setText("Listener: Off")
            
            # ไม่หยุดการพิมพ์ - ให้ยังคงพิมพ์ admin ได้
            # ไม่ปิดเว็บ - ให้ยังคงสามารถส่งข้อความผ่าน admin ได้
            # เว็บจะยังคงเปิดอยู่และสามารถใช้ custom message ได้
            if self.input_field_found:
                self.btn_start_typing.setEnabled(True)
                self.status_label_typing.setText("Typing: Ready (Admin only)")
            else:
                self.btn_start_typing.setEnabled(False)
                self.status_label_typing.setText("Typing: Waiting for input field")

    def update_listener_status(self, status):
        """
        อัพเดตสถานะ Listener ใน GUI
        """
        if status == "connected":
            self.status_label_listener.setText("Listener: Connected")
            self.btn_start_typing.setEnabled(True)
        elif status == "disconnected":
            self.status_label_listener.setText("Listener: Disconnected")
            self.btn_start_typing.setEnabled(False)
        elif status == "failed":
            self.status_label_listener.setText("Listener: Failed to Connect")
            self.btn_start_typing.setEnabled(False)


    # ----------------------
    # Typing control
    # ----------------------
    def start_typing_countdown(self):
        """
        เคลียร์ queue และเริ่ม countdown ก่อนพิมพ์
        """
        # ตรวจสอบว่า input field พร้อมหรือไม่
        if not self.input_field_found:
            self.status_label_typing.setText("Error: Input field not found. Please wait for game to load.")
            return
            
        while not self.comment_queue.empty():
            self.comment_queue.get()
        self.btn_start_typing.hide()
        self.status_label_typing.setText("Typing: Starting in 5 seconds...")
        self.countdown = 5
        self.timer = QTimer()
        self.timer.timeout.connect(self.countdown_tick)
        self.timer.start(1000)

    def countdown_tick(self):
        """
        Countdown tick ทุกวินาที
        """
        self.countdown -= 1
        if self.countdown > 0:
            self.status_label_typing.setText(f"Typing: Starting in {self.countdown} seconds...")
        else:
            self.timer.stop()
            # ตั้งค่าต่าง ๆ ให้ TypingThread
            prefix_enabled = self.prefix_checkbox.isChecked()
            prefix_str = self.prefix_input.text().strip() if prefix_enabled else ""
            
            self.typing_thread.blacklist_enabled = self.blacklist_checkbox.isChecked()
            self.typing_thread.blacklist_str = self.blacklist_input.text().strip()
            self.typing_thread.pre_delay_enabled = self.pre_delay_checkbox.isChecked()
            self.typing_thread.pre_delay_ms = self.pre_delay_input.value()
            self.typing_thread.post_delay_enabled = self.post_delay_checkbox.isChecked()
            self.typing_thread.post_delay_ms = self.post_delay_input.value()
            self.typing_thread.gui = self  # เพื่อใช้ filter_by_group
            self.typing_thread.remove_space_enabled = self.remove_space_checkbox.isChecked()

            # Max Length & Duplicate filter
            self.listener_thread.maxlen_enabled = self.maxlen_checkbox.isChecked()
            self.listener_thread.maxlen_value = self.maxlen_input.value()
            self.listener_thread.duplicate_enabled = self.duplicate_checkbox.isChecked()

            self.typing_thread.start_typing(prefix_enabled, prefix_str)
            self.status_label_typing.setText("Typing: On Typing")
            self.btn_stop_typing.show()
            
            # รีเซ็ตตัวนับการล้มเหลว
            self.input_field_fail_count = 0
            
            # เริ่ม timer ตรวจสอบเกมจบทุก 5 วินาที
            self.game_status_timer.start(5000)

    def stop_typing(self):
        """
        หยุดการพิมพ์ และเคลียร์ queue ทั้งหมด
        """
        self.typing_thread.stop_typing()
        # เคลียร์ queue ทั้งหมด
        while not self.comment_queue.empty():
            try:
                self.comment_queue.get(False)
            except queue.Empty:
                break
        self.status_label_typing.setText("Typing: Stopped")
        self.btn_stop_typing.hide()
        self.btn_start_typing.show()

    def open_web(self):
        url = self.entry_url.text().strip()
        if not url:
            self.status_label_typing.setText("Error: Please enter a valid URL")
            return

        # ปิด driver เก่าถ้ามี (auto close when changing URL)
        if self.driver:
            try:
                self.driver.quit()
                print("Closed previous web session")
            except:
                pass
            self.driver = None
            self.input_field_found = False
            self.btn_start_typing.setEnabled(False)
            self.status_label_typing.setText("Web: Closed previous session")

        try:
            options = Options()
            options.headless = False
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            options.add_argument("--window-size=1920,1080")
            options.add_argument("--disable-web-security")
            options.add_argument("--allow-running-insecure-content")
            options.add_argument("--disable-logging")
            options.add_argument("--disable-gcm")
            options.add_argument("--disable-background-networking")
            options.add_argument("--disable-background-timer-throttling")
            options.add_argument("--disable-renderer-backgrounding")
            options.add_argument("--disable-backgrounding-occluded-windows")
            options.add_argument("--disable-ipc-flooding-protection")
            options.add_argument("--log-level=3")
            options.add_experimental_option('excludeSwitches', ['enable-logging'])
            options.add_experimental_option('useAutomationExtension', False)
            
            self.driver = webdriver.Chrome(options=options)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            # ตั้งค่า timeout
            self.driver.set_page_load_timeout(30)  # 30 วินาที
            
            self.status_label_typing.setText("Web: Loading...")
            self.driver.get(url)
            
            # ตรวจสอบว่าโหลดสำเร็จหรือไม่
            self.driver.implicitly_wait(2)  # ลดเวลารอลง
            
            # แสดงสถานะว่าโหลดเสร็จแล้ว
            self.status_label_typing.setText("Web: Loaded - Checking for input field...")
            
        except Exception as e:
            error_msg = str(e)
            print(f"Error opening web: {error_msg}")
            
            # แสดง error message ที่เข้าใจง่าย
            if "timeout" in error_msg.lower():
                self.status_label_typing.setText("Web Error: Connection timeout - URL may be invalid or unreachable")
            elif "chrome" in error_msg.lower():
                self.status_label_typing.setText("Web Error: Chrome driver not found - Please install ChromeDriver")
            elif "invalid" in error_msg.lower() or "malformed" in error_msg.lower():
                self.status_label_typing.setText("Web Error: Invalid URL format")
            else:
                self.status_label_typing.setText(f"Web Error: {error_msg}")
            
            # ปิด driver ถ้าเปิดได้แต่มีปัญหา
            if self.driver:
                try:
                    self.driver.quit()
                except:
                    pass
                self.driver = None
            
            # แสดงปุ่ม Open Web กลับมา
            self.btn_open_web.show()
            self.btn_close_web.hide()
            return

        # เริ่มตรวจสอบ input field แบบต่อเนื่อง
        self.start_input_field_monitoring()
        
        # แสดงปุ่ม Close Web และซ่อนปุ่ม Open Web
        self.btn_open_web.hide()
        self.btn_close_web.show()
        
        # แสดงสถานะว่าเปิดเว็บสำเร็จ
        self.status_label_typing.setText("Web: Opened - Checking for input field...")

    def start_input_field_monitoring(self):
        """
        เริ่มตรวจสอบ input field แบบต่อเนื่อง
        """
        self.input_field_found = False
        self.btn_start_typing.setEnabled(False)
        self.status_label_typing.setText("Web: Checking for input field...")
        
        # เริ่ม timer ตรวจสอบ input field ทุก 1 วินาที (เร็วขึ้น)
        self.input_check_timer = QTimer()
        self.input_check_timer.timeout.connect(self.check_input_field)
        self.input_check_timer.start(1000)  # ตรวจสอบทุก 1 วินาที
        
        # สร้าง timer ตรวจสอบเกมจบ (จะเริ่มเมื่อเริ่มพิมพ์)
        self.game_status_timer = QTimer()
        self.game_status_timer.timeout.connect(self.check_game_status)
        
        # ตรวจสอบทันทีครั้งแรก (ไม่ต้องรอ 1 วินาที)
        QTimer.singleShot(100, self.check_input_field)

    def check_input_field(self):
        """
        ตรวจสอบว่ามี input field หรือไม่
        """
        if not self.driver:
            self.input_check_timer.stop()
            return

        # ใช้ QTimer.singleShot เพื่อให้ทำงานใน background
        QTimer.singleShot(0, self._check_input_field_async)

    def _check_input_field_async(self):
        """
        ตรวจสอบ input field แบบ async เพื่อไม่ให้ GUI ค้าง
        """
        if not self.driver:
            return

        try:
            # ใช้ selector จาก GUI
            selector = self.entry_selector.text().strip() or 'input[name="word"]'
            input_element = self.driver.find_element(By.CSS_SELECTOR, selector)
            if input_element.is_displayed() and input_element.is_enabled():
                if not self.input_field_found:
                    self.input_field_found = True
                    self.btn_start_typing.setEnabled(True)
                    self.status_label_typing.setText("Web Ready: Input field found - Ready to play!")
                    self.input_check_timer.stop()  # หยุดตรวจสอบเมื่อเจอแล้ว
            else:
                self.input_field_found = False
                self.btn_start_typing.setEnabled(False)
                self.status_label_typing.setText("Web: Input field not ready...")
        except NoSuchElementException:
            self.input_field_found = False
            self.btn_start_typing.setEnabled(False)
            self.status_label_typing.setText("Web: Waiting for game to load...")
        except Exception as e:
            # ถ้าเกิด error อื่นๆ ไม่ให้ GUI ค้าง
            print(f"Input field check error: {e}")
            self.input_field_found = False
            self.btn_start_typing.setEnabled(False)
            self.status_label_typing.setText("Web: Checking...")

    def check_game_status(self):
        """
        ตรวจสอบสถานะเกมว่าจบแล้วหรือไม่ (เฉพาะเมื่อกำลังพิมพ์)
        """
        if not self.driver or not self.typing_thread.running:
            return

        try:
            # ตรวจสอบว่ามี input field หรือไม่
            selector = self.entry_selector.text().strip() or 'input[name="word"]'
            input_element = self.driver.find_element(By.CSS_SELECTOR, selector)
            if not input_element.is_displayed() or not input_element.is_enabled():
                # ถ้า input field หายไป ให้แจ้งสถานะ แต่ไม่หยุดการพิมพ์
                print("Game ended - input field no longer available")
                self.status_label_typing.setText("Game Ended: Waiting for input field...")
        except NoSuchElementException:
            # ถ้าไม่เจอ input field ให้แจ้งสถานะ แต่ไม่หยุดการพิมพ์
            print("Game ended - input field not found")
            self.status_label_typing.setText("Game Ended: Waiting for input field...")
        except Exception as e:
            # ถ้าเกิด error อื่นๆ (เช่น Chrome error) ไม่ให้หยุดการทำงาน
            print(f"Game status check error (ignoring): {e}")
            # ไม่หยุดการทำงาน

    def stop_typing(self):
        self.typing_thread.stop_typing()
        self.status_label_typing.setText("Typing: Stopped")
        self.btn_stop_typing.hide()
        self.btn_start_typing.show()
        
        # หยุด timer ตรวจสอบ input field และเกม
        if hasattr(self, 'input_check_timer'):
            self.input_check_timer.stop()
        if hasattr(self, 'game_status_timer'):
            self.game_status_timer.stop()

    def close_web(self):
        """
        ปิดเว็บและหยุดการทำงานทั้งหมด
        """
        self.stop_typing()
        
        # ปิด Selenium ถ้าเปิดอยู่
        if self.driver:
            try:
                self.driver.quit()
            except Exception as e:
                print(f"Error closing web driver: {e}")
            finally:
                self.driver = None
                self.input_field_found = False
                self.btn_start_typing.setEnabled(False)
                self.status_label_typing.setText("Web: Closed")
                
                # แสดงปุ่ม Open Web และซ่อนปุ่ม Close Web
                self.btn_open_web.show()
                self.btn_close_web.hide()


# ----------------------
# Run App
# ----------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setFont(QFont("Tahoma", 10)) 
    gui = TikTokGUI()
    gui.show()
    sys.exit(app.exec_())
