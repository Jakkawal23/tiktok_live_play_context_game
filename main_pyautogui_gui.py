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
        """
        Loop หลักของ thread
        - ดึงข้อความจาก queue
        - ตรวจ prefix
        - filter (group / blacklist / remove space)
        - delay ก่อนและหลังพิมพ์
        - พิมพ์ข้อความด้วย pynput
        """
        while True:
            if self.running and not self.comment_queue.empty():
                text = self.comment_queue.get()
                
                # ตรวจ prefix
                if self.prefix_enabled:
                    if not text.startswith(self.prefix_str):
                        continue
                    text = text[len(self.prefix_str):]  # ตัด prefix ออก
                
                # ลบ emoji / สัญลักษณ์
                text_to_type = clean_text(text)

                # filter by group (Thai, English, Number, Special)
                if hasattr(self, "gui"):
                    text_to_type = filter_by_group(text_to_type, self.gui)

                # filter blacklist ถ้าเปิด
                if hasattr(self, "blacklist_enabled") and self.blacklist_enabled:
                    text_to_type = apply_blacklist(text_to_type, self.blacklist_str)

                # remove space ถ้าเปิด
                if hasattr(self, "remove_space_enabled") and self.remove_space_enabled:
                    text_to_type = text_to_type.replace(" ", "")
                    words = text_to_type.split()
                else:
                    words = [text_to_type]

                # pre-typing delay
                if getattr(self, "pre_delay_enabled", False):
                    time.sleep(self.pre_delay_ms / 1000.0)

                # พิมพ์ข้อความ
                for word in words:
                    for char in word:
                        self.keyboard.type(char)
                        time.sleep(random.uniform(0.05, 0.15))  # typing speed random
                    self.keyboard.press(Key.enter)
                    self.keyboard.release(Key.enter)

                # ลบข้อความออกจาก pending_messages (duplicate filter)
                if hasattr(self, "gui") and hasattr(self.gui.listener_thread, "pending_messages"):
                    self.gui.listener_thread.pending_messages.discard(text)
                    
                # post-typing delay
                if getattr(self, "post_delay_enabled", False):
                    time.sleep(self.post_delay_ms / 1000.0)

                time.sleep(0.1)  # ป้องกัน loop หนักเกินไป
            else:
                time.sleep(0.1)  # queue ว่าง / หยุด typing → sleep

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

        # -------------------
        # Event callback จาก TikTokLiveClient
        # -------------------
        @self.client.on(CommentEvent)
        async def on_comment(event: CommentEvent):
            text = event.comment.strip()
            if not text:
                return

            self.gui_callback(event.user.nickname, text)  # แสดงใน GUI

            # Max length filter
            maxlen_enabled = getattr(self, 'maxlen_enabled', False)
            maxlen = getattr(self, 'maxlen_value', 2000)
            if maxlen_enabled and len(text) > maxlen:
                return

            # Duplicate filter
            duplicate_enabled = getattr(self, 'duplicate_enabled', False)
            if duplicate_enabled and text in self.pending_messages:
                return

            # ส่งข้อความเข้า Queue
            self.typing_queue.put(text)
            if duplicate_enabled:
                self.pending_messages.add(text)

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
        self.task = self.loop.create_task(self.client.run())

        try:
            while self.running and not self.task.done():
                # ตรวจ loop ทุก 0.1 วินาที
                self.loop.run_until_complete(asyncio.sleep(0.1))
        except Exception as e:
            self.status_callback("failed")
            print("Listener error:", e)
        finally:
            if not self.client._closed:
                self.loop.run_until_complete(self.client.close())
            self.loop.close()

    def stop(self):
        """
        หยุด Listener และปิด event loop
        """
        self.running = False
        if self.loop and not self.loop.is_closed():
            asyncio.run_coroutine_threadsafe(self.client.close(), self.loop)


# ----------------------
# GUI
# ----------------------
class TikTokGUI(QWidget):
    new_comment_signal = pyqtSignal(str, str)  # nickname, text

    def __init__(self):
        super().__init__()
        self.setWindowTitle("TikTok Live Auto Typer")
        self.setWindowIcon(QIcon("program_icon.ico"))
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

    # ----------------------
    # Display comment (main thread)
    # ----------------------
    def display_comment(self, nickname, text):
        display_text = f"{nickname}: {text}\n"
        self.text_area.moveCursor(self.text_area.textCursor().End)
        self.text_area.insertPlainText(display_text)
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

            # สร้าง listener
            self.listener_thread = TikTokListener(
                uid,
                self.new_comment_signal.emit,
                self.comment_queue,
                self.update_listener_status
            )
            self.listener_thread.daemon = True
            self.listener_thread.start()

            self.btn_listener.setText("Stop Listener")
            self.btn_listener.setStyleSheet("background-color: red; color: white")
            self.status_label_listener.setText("Listener: Connecting...")
            self.btn_start_typing.setEnabled(False)
        else:
            # กด Stop Listener
            if self.listener_thread:
                self.listener_thread.gui_callback = lambda n,t: None
                self.listener_thread.stop()
                self.listener_thread.join(timeout=2)
                self.listener_thread = None

            self.btn_listener.setText("Start Listener")
            self.btn_listener.setStyleSheet("background-color: green; color: white")
            self.status_label_listener.setText("Listener: Off")
            self.btn_start_typing.setEnabled(False)
            self.status_label_typing.setText("Typing: Idle")
            self.stop_typing()

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

    def stop_typing(self):
        """
        หยุดการพิมพ์
        """
        self.typing_thread.stop_typing()
        self.status_label_typing.setText("Typing: Stopped")
        self.btn_stop_typing.hide()
        self.btn_start_typing.show()


# ----------------------
# Run App
# ----------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setFont(QFont("Tahoma", 10)) 
    gui = TikTokGUI()
    gui.show()
    sys.exit(app.exec_())
