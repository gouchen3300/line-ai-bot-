from fastapi import FastAPI, Request, HTTPException
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi, TextMessage, ReplyMessageRequest
from linebot.v3.messaging.models import TextMessage as TextMessageModel
from linebot.v3.webhook import WebhookParser, InvalidSignatureError
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from dotenv import load_dotenv
import feedparser
import os

load_dotenv()

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")

if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_CHANNEL_SECRET:
    raise ValueError("Missing environment variables")

app = FastAPI()

configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
client = ApiClient(configuration)
messaging_api = MessagingApi(client)
parser = WebhookParser(LINE_CHANNEL_SECRET)

@app.get("/")
async def root():
    return {"message": "LINE bot is running"}

@app.post("/webhook/line")
async def line_webhook(request: Request):
    body = await request.body()
    signature = request.headers.get("X-Line-Signature", "")

    try:
        events = parser.parse(body.decode("utf-8"), signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    for event in events:
        if isinstance(event, MessageEvent) and isinstance(event.message, TextMessageContent):
            text = event.message.text.strip()
            reply_messages = route_command(text)

            messaging_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=reply_messages
                )
            )

    return "OK"

def route_command(text: str):
    if text.startswith("#英文"):
        return handle_english(text)

    if text.startswith("#早安圖"):
        return handle_greeting()

    if text.startswith("#新聞"):
        return handle_news()

    return [TextMessageModel(text="請輸入 #英文、#早安圖 或 #新聞")]

def handle_english(text: str):
    content = text.replace("#英文", "", 1).strip()

    if not content:
        return [TextMessageModel(text="請輸入英文句子，例如：#英文 How are you doing?")]

    reply = f"""英文句子：
{content}

中文意思：
（請先自行翻譯）

文法重點：
（句型、時態、介系詞、主詞動詞一致）

單字重點：
（列出 1～3 個關鍵單字）

更自然說法：
（如果有更口語的講法，可寫在這裡）

例句：
（再提供 1 句相似句）"""

    return [TextMessageModel(text=reply)]

def handle_greeting():
    return [TextMessageModel(text="早安！祝你今天順利。")]

def handle_news():
    rss_url = "https://tw.news.yahoo.com/rss/"
    feed = feedparser.parse(rss_url)

    if not feed.entries:
        return [TextMessageModel(text="目前沒有抓到新聞。")]

    lines = ["今日新聞摘要："]
    for i, entry in enumerate(feed.entries[:5], 1):
        title = getattr(entry, "title", "無標題")
        link = getattr(entry, "link", "")
        lines.append(f"{i}. {title}\n{link}")

    return [TextMessageModel(text="\n\n".join(lines))]
