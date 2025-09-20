import time
import re
from TikTokLive import TikTokLiveClient
from TikTokLive.events import CommentEvent
from pynput.keyboard import Controller, Key

keyboard = Controller()

client = TikTokLiveClient(unique_id="@username") 

def clean_thai(text):
    # เอาเฉพาะตัวอักษรไทย, ตัวเลข และ space
    return re.sub(r'[^ก-๙0-9\s]+', '', text)

print("คุณมีเวลา 5 วินาที คลิกไปที่ Notepad / ช่อง input เกม")
time.sleep(5)

@client.on(CommentEvent)
async def on_comment(event: CommentEvent):
    text = clean_thai(event.comment).strip()
    if not text:
        return

    print(f"[Chat] {event.user.nickname}: {text}")

    # พิมพ์ข้อความ
    for char in text:
        keyboard.type(char)

    # กด Enter จริงๆ
    keyboard.press(Key.enter)
    keyboard.release(Key.enter)

if __name__ == "__main__":
    client.run()
