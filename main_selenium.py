from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from TikTokLive import TikTokLiveClient
from TikTokLive.events import CommentEvent

# เปลี่ยน URL เกมตรงนี้
GAME_URL = "https://example.com/game"

# เปิด Chrome ด้วย Selenium
driver = webdriver.Chrome()
driver.get(GAME_URL)

# หา input box (ต้องแก้ selector ให้ตรงกับเว็บเกมจริง)
input_box = driver.find_element(By.CSS_SELECTOR, "input")

# TikTok client
client = TikTokLiveClient(unique_id="@username")

@client.on(CommentEvent)
async def on_comment(event: CommentEvent):
    text = event.comment
    print(f"[Chat] {event.user.nickname}: {text}")

    # ใส่ข้อความลงใน input ของเกม
    input_box.send_keys(text)
    input_box.send_keys(Keys.ENTER)

if __name__ == "__main__":
    client.run()
