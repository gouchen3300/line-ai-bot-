from fastapi import FastAPI, Request, HTTPException
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
from dotenv import load_dotenv
import os
import google.generativeai as genai

load_dotenv()

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_CHANNEL_SECRET or not GEMINI_API_KEY:
    raise ValueError("Missing environment variables")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.0-flash")

app = FastAPI()
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

@app.get("/")
async def root():
    return {"message": "LINE AI Bot is running!"}

@app.post("/webhook/line")
async def line_webhook(request: Request):
    signature = request.headers.get("X-Line-Signature", "")
    body = await request.body()
    body_text = body.decode("utf-8")

    try:
        handler.handle(body_text, signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    return "OK"

def ask_gemini(prompt: str) -> str:
    try:
        response = model.generate_content(prompt)
        return response.text
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

@handler.add(MessageEvent, message=TextMessage)
def handle_text_message(event):
    reply_text = route_command(event.message.text)
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))
