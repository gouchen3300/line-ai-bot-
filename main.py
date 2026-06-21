from fastapi import FastAPI, Request, HTTPException
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import os
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not CHANNEL_ACCESS_TOKEN or not CHANNEL_SECRET or not GEMINI_API_KEY:
    raise ValueError("Missing environment variables")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.0-flash")

app = FastAPI()
line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

@app.get("/")
async def root():
    return {"message": "LINE AI Bot is running!"}

@app.post("/webhook/line")
async def line_webhook(request: Request):
    signature = request.headers.get("X-Line-Signature", "")
    body = await request.body()
    try:
        handler.handle(body.decode("utf-8"), signature)
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
        prompt = f"""
你是一位英文老師，請用繁體中文回答。
請分析這句英文：
{content}

請包含：
1. 中文意思
2. 文法重點
3. 單字重點
4. 更自然的口語說法
5. 1 個例句
回答要清楚簡潔。
"""
        return ask_gemini(prompt)

    if text.startswith("#園藝"):
        content = text.replace("#園藝", "").strip()
        if not content:
            return "請輸入園藝問題，例如：#園藝 多肉植物多久澆一次水？"
        prompt = f"""
你是一位專業園藝小幫手，請用繁體中文回答。
問題是：
{content}

請包含：
1. 照顧方式
2. 澆水建議
3. 日照需求
4. 土壤建議
5. 常見問題與注意事項
回答要實用、簡潔。
"""
        return ask_gemini(prompt)

    if text.startswith("#早安圖"):
        return "早安圖功能我已收到，下一步會幫你改成圖片版本。"

    return ask_gemini(f"請用繁體中文簡潔回答這句話：{text}")

@handler.add(MessageEvent, message=TextMessage)
def handle_text_message(event):
    reply_text = route_command(event.message.text)
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply_text)
    )
