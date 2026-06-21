from fastapi import FastAPI, Request, HTTPException
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi, TextMessage, ReplyMessageRequest
from linebot.v3.messaging.models import TextMessage as TextMessageModel
from linebot.v3.webhook import WebhookParser
from linebot.v3.webhook import InvalidSignatureError
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from dotenv import load_dotenv
from google import genai
import os

load_dotenv()

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_CHANNEL_SECRET or not GEMINI_API_KEY:
    raise ValueError("Missing environment variables")

app = FastAPI()

configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
client = ApiClient(configuration)
messaging_api = MessagingApi(client)
parser = WebhookParser(LINE_CHANNEL_SECRET)

genai_client = genai.Client(api_key=GEMINI_API_KEY)

@app.get("/")
async def root():
    return {"message": "LINE AI Bot is running!"}

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
            reply_text = route_command(event.message.text)
            messaging_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessageModel(text=reply_text)]
                )
            )

    return "OK"

def ask_gemini(prompt: str) -> str:
    try:
        response = genai_client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt
        )
        return response.text or "AI 沒有回傳內容"
    except Exception as e:
        return f"AI 錯誤：{str(e)}"

def route_command(text: str) -> str:
    if text.startswith("#英文"):
        content = text.replace("#英文", "").strip()
        if not content:
            return "請輸入英文句子，例如：#英文 How are you doing?"
        return ask_gemini(f"你是一位英文老師，請用繁體中文分析這句英文：{content}。請包含中文意思、文法重點、單字重點、自然口語說法、例句。")

    if text.startswith("#園藝"):
        content = text.replace("#園藝", "").strip()
        if not content:
            return "請輸入園藝問題，例如：#園藝 多肉植物多久澆一次水？"
        return ask_gemini(f"你是一位專業園藝小幫手，請用繁體中文回答這個問題：{content}。請包含照顧方式、澆水建議、日照需求、土壤建議、常見問題與注意事項。")

    if text.startswith("#早安圖"):
        return "早安圖功能已收到，下一步我會幫你改成圖片版。"

    return ask_gemini(f"請用繁體中文簡潔回答這句話：{text}")
