from TikTokLive import TikTokLiveClient
from TikTokLive.events import CommentEvent, GiftEvent, ConnectEvent

# Change username
client = TikTokLiveClient(unique_id="@channlename")

@client.on(ConnectEvent)
async def on_connect(event: ConnectEvent):
    print(f"Connected to @{event.unique_id} — room id: {client.room_id}")

@client.on(CommentEvent)
async def on_comment(event: CommentEvent):
    print(f"[Chat] {event.user.nickname}: {event.comment}")

@client.on(GiftEvent)
async def on_gift(event: GiftEvent):
    print(f"[Gift] {event.user.unique_id} sent \"{event.gift.name}\"")

if __name__ == "__main__":
    client.run()
