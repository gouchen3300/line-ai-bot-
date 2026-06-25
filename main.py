import os
import re
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
from dotenv import load_dotenv
import requests

# 【安全防線 1】暫時註解掉 load_dotenv()，確保專案內的舊舊 .env 檔案不會覆蓋掉 Render 後台的正確設定
# load_dotenv()

# 安全讀取 Render 後台設定的環境變數
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

@app.get("/")
async def root():
    return {"message": "AI智慧小幫手 (除錯完全體) 正在運行中"}

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
                
                # 🤖 連線至 Google Gemini AI
                api_url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
                headers = {"Content-Type": "application/json"}
                payload = {"contents": [{"parts": [{"text": user_message}]}]}
                
                try:
                    response = requests.post(api_url, json=payload, headers=headers, timeout=15)
                    res_json = response.json()
                    
                    if response.status_code == 200:
                        reply_text = res_json['candidates'][0]['content']['parts'][0]['text']
                    else:
                        error_msg = res_json.get('error', {}).get('message', '未知錯誤')
                        
                        # 【安全防線 2】如果失敗，安全地遮罩金鑰，並顯示其長度，用來核對是否夾帶空格或變形
                        debug_key = str(GEMINI_API_KEY)
                        masked_key = f"{debug_key[:4]}...{debug_key[-4:]}" if len(debug_key) > 8 else debug_key
                        
                        reply_text = (
                            f"【Google拒絕連線】\n"
                            f"代碼: {response.status_code}\n"
                            f"原因: {error_msg}\n"
                            f"-----------------\n"
                            f"💡 系統除錯資訊：\n"
                            f"抓取到的變數開頭/結尾: {masked_key}\n"
                            f"金鑰字串總長度: {len(debug_key)} 個字元\n"
                            f"(提示：標準金鑰長度通常為 39 個字元，且開頭為 AIza)"
                        )
                except Exception as ai_err:
                    reply_text = f"【AI連線失敗】:\n{str(ai_err)}"

                # 回傳給 LINE 使用者
                messaging_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text=reply_text)]
                    )
                )
        except Exception as e:
            print(f"Event error: {e}")

    return "OK"
