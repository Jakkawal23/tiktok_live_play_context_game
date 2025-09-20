import sys
import re
import queue
import threading
import time
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QPushButton,
    QTextEdit, QVBoxLayout, QHBoxLayout, QCheckBox
)
from PyQt5.QtCore import QTimer
from TikTokLive import TikTokLiveClient
from TikTokLive.events import CommentEvent
from pynput.keyboard import Controller, Key
import random

# ----------------------
# ฟังก์ชันช่วยเหลือ
# ----------------------
def clean_thai(text):
    # return re.sub(r'[^ก-๙0-9\s]+', '', text)
    return re.sub(r'[^\u0E00-\u0E7F0-9\s]+', '', text)

# ----------------------
# Typing Thread
# ----------------------
class TypingThread(threading.Thread):
    def __init__(self, comment_queue, prefix_enabled=False, prefix_str=""):
        super().__init__()
        self.comment_queue = comment_queue
        self.keyboard = Controller()
        self.running = False
        self.prefix_enabled = prefix_enabled
        self.prefix_str = prefix_str

    def start_typing(self, prefix_enabled=False, prefix_str=""):
        self.prefix_enabled = prefix_enabled
        self.prefix_str = prefix_str
        self.running = True

    def stop_typing(self):
        self.running = False

    def run(self):
        while True:
            if self.running and not self.comment_queue.empty():
                text = self.comment_queue.get()
                # ตรวจ prefix
                if self.prefix_enabled:
                    if not text.startswith(self.prefix_str):
                        continue
                    text = text[len(self.prefix_str):]  # ตัด prefix ออก
                for char in text:
                    self.keyboard.type(char)
                    # delay สั้น ๆ เพื่อให้เหมือนคนพิมพ์
                    time.sleep(random.uniform(0.05, 0.15))  # 50-150 ms ต่อแต่ละตัว
                self.keyboard.press(Key.enter)
                self.keyboard.release(Key.enter)
                time.sleep(0.1)
            else:
                time.sleep(0.1)

# ----------------------
# TikTok Listener Thread
# ----------------------
class TikTokListener(threading.Thread):
    def __init__(self, unique_id, display_callback):
        super().__init__()
        self.client = TikTokLiveClient(unique_id=unique_id)
        self.display_callback = display_callback
        self.running = True
        self.new_comment_callback = None  # จะใช้สำหรับส่ง comment ให้ TypingThread

        @self.client.on(CommentEvent)
        async def on_comment(event: CommentEvent):
            if self.running:
                text = clean_thai(event.comment).strip()
                if text:
                    self.display_callback(event.user.nickname, text)
                    if self.new_comment_callback is not None:
                        self.new_comment_callback(text)  # ส่งให้ TypingThread

    def run(self):
        self.client.run()

    def stop(self):
        self.running = False

# ----------------------
# GUI
# ----------------------
class TikTokGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TikTok Live Auto Typer")
        self.comment_queue = queue.Queue()

        self.listener_thread = None
        self.typing_thread = TypingThread(self.comment_queue)
        self.typing_thread.daemon = True
        self.typing_thread.start()

        layout = QVBoxLayout()

        # Unique ID input
        h_uid = QHBoxLayout()
        h_uid.addWidget(QLabel("TikTok Unique ID:"))
        self.entry_uid = QLineEdit()
        h_uid.addWidget(self.entry_uid)
        layout.addLayout(h_uid)

        # Prefix checkbox + input
        h_prefix = QHBoxLayout()
        self.prefix_checkbox = QCheckBox("Enable Prefix Filter")
        self.prefix_input = QLineEdit()
        self.prefix_input.setPlaceholderText("Enter prefix (e.g., _ )")
        h_prefix.addWidget(self.prefix_checkbox)
        h_prefix.addWidget(self.prefix_input)
        layout.addLayout(h_prefix)

        # Comment display
        self.text_area = QTextEdit()
        self.text_area.setReadOnly(True)
        layout.addWidget(self.text_area)

        # Buttons
        h_buttons = QHBoxLayout()
        self.btn_listener = QPushButton("Start Listener")
        self.btn_listener.setStyleSheet("background-color: green; color: white")
        self.btn_listener.clicked.connect(self.toggle_listener)
        h_buttons.addWidget(self.btn_listener)

        self.btn_start_typing = QPushButton("Start Typing")
        self.btn_start_typing.clicked.connect(self.start_typing_countdown)
        h_buttons.addWidget(self.btn_start_typing)

        self.btn_stop_typing = QPushButton("Stop Typing")
        self.btn_stop_typing.clicked.connect(self.stop_typing)
        self.btn_stop_typing.hide()
        h_buttons.addWidget(self.btn_stop_typing)

        layout.addLayout(h_buttons)

        # Status label
        self.status_label = QLabel("Status: Idle")
        layout.addWidget(self.status_label)

        self.setLayout(layout)

    # ----------------------
    # Methods
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
        if self.listener_thread is None:
            # Start Listener
            uid = self.entry_uid.text().strip()
            if not uid:
                return
            self.listener_thread = TikTokListener(uid, self.display_comment)
            # ตั้ง callback ให้ TypingThread รับ comment ใหม่
            self.listener_thread.new_comment_callback = lambda txt: self.comment_queue.put(txt)
            self.listener_thread.daemon = True
            self.listener_thread.start()
            self.btn_listener.setText("Stop Listener")
            self.btn_listener.setStyleSheet("background-color: red; color: white")
            self.status_label.setText("Status: Listener On")
        else:
            # Stop Listener
            self.listener_thread.stop()
            self.listener_thread = None
            self.btn_listener.setText("Start Listener")
            self.btn_listener.setStyleSheet("background-color: green; color: white")
            self.status_label.setText("Status: Listener Off")

    # ----------------------
    # Typing control
    # ----------------------
    def start_typing_countdown(self):
        # ล้างคิวเก่าก่อน
        while not self.comment_queue.empty():
            self.comment_queue.get()
        self.btn_start_typing.hide()
        self.status_label.setText("Status: Typing starts in 5 seconds...")
        self.countdown = 5
        self.timer = QTimer()
        self.timer.timeout.connect(self.countdown_tick)
        self.timer.start(1000)

    def countdown_tick(self):
        self.countdown -= 1
        if self.countdown > 0:
            self.status_label.setText(f"Status: Typing starts in {self.countdown} seconds...")
        else:
            self.timer.stop()
            # เริ่มพิมพ์ โดยตรวจ prefix
            prefix_enabled = self.prefix_checkbox.isChecked()
            prefix_str = self.prefix_input.text().strip() if prefix_enabled else ""
            self.typing_thread.start_typing(prefix_enabled, prefix_str)
            self.status_label.setText("Status: On Typing")
            self.btn_stop_typing.show()

    def stop_typing(self):
        self.typing_thread.stop_typing()
        self.status_label.setText("Status: Typing Stopped")
        self.btn_stop_typing.hide()
        self.btn_start_typing.show()

# ----------------------
# Run App
# ----------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    gui = TikTokGUI()
    gui.show()
    sys.exit(app.exec_())
