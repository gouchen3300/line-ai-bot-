from fastapi import FastAPI, Request, HTTPException
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi, TextMessage, ReplyMessageRequest
from linebot.v3.messaging.models import TextMessage as TextMessageModel
from linebot.v3.webhook import WebhookParser, InvalidSignatureError
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from dotenv import load_dotenv
import feedparser
import os
import re

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

QUESTION_STARTERS = {
    "what", "where", "when", "why", "who", "how",
    "do", "does", "did", "is", "are", "am", "was", "were",
    "can", "could", "will", "would", "should", "have", "has", "had"
}

BE_VERBS = {"am", "is", "are", "was", "were", "be", "been", "being"}

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

def detect_sentence_type(sentence: str) -> str:
    s = sentence.strip().lower()
    s = s.rstrip(".!?")

    if not s:
        return "unknown"

    first_word = re.split(r"\s+", s)[0]

    if sentence.strip().endswith("?") or first_word in QUESTION_STARTERS:
        return "question"

    words = set(re.findall(r"\b[a-z']+\b", s))
    if words & BE_VERBS:
        return "be_verb"

    return "general_verb"

def handle_english(text: str):
    content = text.replace("#英文", "", 1).strip()

    if not content:
        return [TextMessageModel(text="請輸入英文句子，例如：#英文 How are you doing?")]

    sentence_type = detect_sentence_type(content)

    if sentence_type == "question":
        reply = f"""句型判斷：問句

英文句子：
{content}

中文意思：
（請先自行翻譯）

文法重點：
1. 這句是問句。
2. 觀察句首助動詞 / 疑問詞。
3. 注意問句語序與語氣。

回答方向：
（可回答 Yes/No 或完整句）

例句：
（請補一個相似問句）"""

    elif sentence_type == "be_verb":
        reply = f"""句型判斷：be 動詞句

英文句子：
{content}

中文意思：
（請先自行翻譯）

文法重點：
1. 這句含有 be 動詞。
2. 常見結構：主詞 + be 動詞 + 補語。
3. be 動詞後面常接形容詞、名詞或介系詞片語。

單字重點：
（列出關鍵單字）

例句：
（請補一個相似句）"""

    else:
        reply = f"""句型判斷：一般動詞句

英文句子：
{content}

中文意思：
（請先自行翻譯）

文法重點：
1. 這句不是問句，也不是典型 be 動詞句。
2. 常見結構：主詞 + 動詞 + 受詞 / 補語。
3. 注意第三人稱單數、時態與動詞變化。

單字重點：
（列出關鍵單字）

例句：
（請補一個相似句）"""

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
