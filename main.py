import os
import requests
from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException

from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
)
from linebot.v3.webhook import WebhookParser, InvalidSignatureError
from linebot.v3.webhooks import MessageEvent, TextMessageContent

load_dotenv()

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_CHANNEL_SECRET or not GEMINI_API_KEY:
    raise ValueError("錯誤：環境變數設定不完整，請確認 Render 後台的 Environment 設定。")

app = FastAPI()

configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
client = ApiClient(configuration)
messaging_api = MessagingApi(client)
parser = WebhookParser(LINE_CHANNEL_SECRET)

GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"


@app.get("/")
async def root():
    return {"message": "AI智慧小幫手 (Gemini) 正在運行中"}


def ask_gemini(user_message: str) -> str:
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": GEMINI_API_KEY,
    }

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": user_message}
                ]
            }
        ]
    }

    try:
        response = requests.post(GEMINI_URL, json=payload, headers=headers, timeout=20)
    except requests.RequestException as e:
        return f"【AI連線失敗】\n原因: {str(e)}"

    try:
        res_json = response.json()
    except Exception:
        return f"【Google回應異常】\n狀態碼: {response.status_code}\n內容: {response.text[:500]}"

    if response.status_code != 200:
        error_msg = res_json.get("error", {}).get("message", "未知錯誤")
        return f"【Google拒絕連線】\n原因: {error_msg}"

    try:
        candidates = res_json.get("candidates", [])
        if not candidates:
            return "【AI回應空白】\nGoogle沒有回傳 candidates。"

        parts = candidates[0].get("content", {}).get("parts", [])
        if not parts:
            return "【AI回應空白】\nGoogle沒有回傳內容段落。"

        reply_text = parts[0].get("text", "")
        if not reply_text.strip():
            return "【AI回應空白】\n模型回覆是空字串。"

        return reply_text
    except Exception as e:
        return f"【AI解析失敗】\n原因: {str(e)}"


@app.post("/webhook/line")
async def line_webhook(request: Request):
    body = await request.body()
    signature = request.headers.get("X-Line-Signature", "")

    try:
        events = parser.parse(body.decode("utf-8"), signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    for event in events:
        try:
            if isinstance(event, MessageEvent) and isinstance(event.message, TextMessageContent):
                user_message = event.message.text.strip()

                if not user_message:
                    reply_text = "請輸入文字訊息。"
                else:
                    reply_text = ask_gemini(user_message)

                messaging_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text=reply_text[:5000])]
                    )
                )
        except Exception as e:
            print(f"Event error: {e}")

    return {"status": "ok"}
