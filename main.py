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

QUESTION_WORDS = {
    "what", "where", "when", "why", "who", "whom", "whose", "which", "how"
}

BE_FORMS = {"am", "is", "are", "was", "were"}
DO_FORMS = {"do", "does", "did"}
MODALS = {
    "can", "could", "will", "would", "shall", "should",
    "may", "might", "must"
}
AUX_FORMS = BE_FORMS | DO_FORMS | MODALS | {"have", "has", "had"}

COMMON_VERBS = {
    "am", "is", "are", "was", "were", "be", "been", "being",
    "do", "does", "did", "have", "has", "had",
    "like", "likes", "play", "plays", "eat", "eats", "read", "reads",
    "go", "goes", "make", "makes", "take", "takes", "see", "sees",
    "want", "wants", "need", "needs", "know", "knows", "say", "says",
    "work", "works", "study", "studies", "live", "lives",
    "swim", "swims", "run", "runs", "walk", "walks", "buy", "buys",
    "watch", "watches", "teach", "teaches", "use", "uses",
    "help", "helps", "talk", "talks", "need", "needs", "feel", "feels"
}

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
        try:
            if isinstance(event, MessageEvent) and isinstance(event.message, TextMessageContent):
                text = event.message.text.strip()
                reply_messages = route_command(text)

                if reply_messages:
                    messaging_api.reply_message(
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=reply_messages
                        )
                    )
        except Exception as e:
            print(f"Event error: {e}")

    return "OK"

def route_command(text: str):
    if not text:
        return [TextMessage(text="請輸入 #英文、#早安圖 或 #新聞")]

    if text.startswith("#英文"):
        return handle_english(text)

    if text.startswith("#早安圖"):
        return handle_greeting()

    if text.startswith("#新聞"):
        return handle_news()

    return [TextMessage(text="請輸入 #英文、#早安圖 或 #新聞")]

def get_first_word(sentence: str) -> str:
    s = sentence.strip()
    if not s:
        return ""
    m = re.match(r"^\s*([A-Za-z']+)", s)
    return m.group(1).lower() if m else ""

def detect_sentence_type(sentence: str) -> tuple[str, str]:
    s = sentence.strip()
    normalized = s.lower().rstrip(".!?")

    if not normalized:
        return "unknown", ""

    first_word = get_first_word(s)
    words = set(re.findall(r"\b[a-z']+\b", normalized))

    if first_word in QUESTION_WORDS:
        return "wh_question", first_word

    if first_word in BE_FORMS:
        if s.endswith("?"):
            return "be_question", first_word
        return "be_statement", first_word

    if first_word in DO_FORMS:
        if s.endswith("?"):
            return "do_question", first_word
        return "do_statement", first_word

    if first_word in MODALS:
        if s.endswith("?"):
            return "modal_question", first_word
        return "modal_statement", first_word

    if words & BE_FORMS:
        return "be_statement", first_word

    return "general_statement", first_word

def split_simple_sentence(sentence: str):
    s = sentence.strip().rstrip(".!?")
    tokens = re.findall(r"[A-Za-z']+|[,]", s)
    lower_tokens = [t.lower() for t in tokens if t != ","]

    subject = ""
    verb = ""
    object_part = ""
    complement = ""

    if not lower_tokens:
        return subject, verb, object_part, complement

    if lower_tokens[0] in QUESTION_WORDS or lower_tokens[0] in AUX_FORMS:
        if len(tokens) >= 2:
            subject = tokens[1]
        if len(tokens) >= 3:
            verb = tokens[2]
        if len(tokens) >= 4:
            rest = tokens[3:]
            if lower_tokens[0] in BE_FORMS or lower_tokens[0] in MODALS or lower_tokens[0] in DO_FORMS:
                complement = " ".join(rest)
            else:
                object_part = " ".join(rest)
        return subject, verb, object_part, complement

    subject = tokens[0]

    if len(tokens) >= 2:
        verb = tokens[1]

    if len(tokens) >= 3:
        if verb.lower() in BE_FORMS:
            complement = " ".join(tokens[2:])
        else:
            object_part = " ".join(tokens[2:])

    return subject, verb, object_part, complement

def format_table(rows):
    label_width = max(len(r[0]) for r in rows)
    value_width = max(len(r[1]) for r in rows)

    top = f"╔{'═' * (label_width + 2)}╦{'═' * (value_width + 2)}╗"
    mid = f"╠{'═' * (label_width + 2)}╬{'═' * (value_width + 2)}╣"
    bottom = f"╚{'═' * (label_width + 2)}╩{'═' * (value_width + 2)}╝"

    lines = [top]
    for i, (label, value) in enumerate(rows):
        lines.append(f"║ {label.ljust(label_width)} ║ {value.ljust(value_width)} ║")
        if i != len(rows) - 1:
            lines.append(mid)
    lines.append(bottom)
    return "\n".join(lines)

def handle_english(text: str):
    content = text.replace("#英文", "", 1).strip()

    if not content:
        return [TextMessage(text="請輸入英文句子，例如：#英文 How are you doing?")]

    sentence_type, first_word = detect_sentence_type(content)
    subject, verb, obj, complement = split_simple_sentence(content)

    if sentence_type == "wh_question":
        type_name = "疑問詞問句"
        explanation = "1. 這句以疑問詞開頭。\n2. 常見疑問詞：what, where, when, why, who, how。\n3. 通常用來詢問資訊，而不是單純 Yes/No。"
        answer_hint = "回答方向：用完整句回答，說明原因、時間、地點或方式。"
    elif sentence_type == "be_question":
        type_name = "be 動詞問句"
        explanation = "1. 這句以 be 動詞開頭。\n2. 句型通常是：Be 動詞 + 主詞 + 補語？\n3. 常見於身分、狀態、位置的提問。"
        answer_hint = "回答方向：常用 Yes/No，或補充詳細狀態。"
    elif sentence_type == "do_question":
        type_name = "do 問句"
        explanation = "1. 這句以 do / does / did 開頭。\n2. 句型通常是：Do/Does/Did + 主詞 + 原形動詞？\n3. 常見於一般動詞的提問。"
        answer_hint = "回答方向：常用 Yes/No，或簡短說明動作。"
    elif sentence_type == "modal_question":
        type_name = "情態助動詞問句"
        explanation = "1. 這句以情態助動詞開頭。\n2. 常見情態助動詞：can, could, will, would, should, may, might, must。\n3. 常用來表示能力、請求、建議、可能性。"
        answer_hint = "回答方向：依情態語氣回答，例如可以、可能、建議、義務。"
    elif sentence_type == "be_statement":
        type_name = "be 動詞陳述句"
        explanation = "1. 這句是陳述句。\n2. 句中含有 be 動詞。\n3. 常見結構：主詞 + be 動詞 + 補語。"
        answer_hint = "回答方向：說明身分、狀態、地點或特徵。"
    elif sentence_type == "do_statement":
        type_name = "一般動詞陳述句"
        explanation = "1. 這句是陳述句。\n2. 可視為一般動作句。\n3. 常見結構：主詞 + 動詞 + 受詞 / 補語。"
        answer_hint = "回答方向：說明動作、習慣或發生的事件。"
    elif sentence_type == "modal_statement":
        type_name = "情態助動詞陳述句"
        explanation = "1. 這句是陳述句。\n2. 句中含有情態助動詞。\n3. 常用來表達能力、可能、建議、義務或意願。"
        answer_hint = "回答方向：說明可能性、建議或能力。"
    else:
        type_name = "一般陳述句"
        explanation = "1. 這句不是明顯問句。\n2. 先視為一般動詞陳述句。\n3. 常見結構：主詞 + 動詞 + 受詞 / 補語。"
        answer_hint = "回答方向：先看主詞、動詞、受詞，再補中文意思。"

    rows = [
        ("欄位", "內容"),
        ("句首類型", first_word or "無法判斷"),
        ("句型分類", type_name),
        ("主詞", subject or "—"),
        ("動詞", verb or "—"),
        ("受詞", obj or "—"),
        ("補語", complement or "—"),
    ]

    table_text = format_table(rows)

    reply = f"""英文句子：
{content}

句型判斷：
{type_name}

判斷說明：
{explanation}

{answer_hint}

主詞動詞分析：
{table_text}

中文意思：
（請先自行翻譯）

單字重點：
（列出 1～3 個關鍵單字）

例句：
（再提供 1 句相似句）"""

    return [TextMessage(text=reply)]

def handle_greeting():
    return [TextMessage(text="早安！祝你今天順利。")]

def handle_news():
    rss_url = "https://tw.news.yahoo.com/rss/"
    try:
        feed = feedparser.parse(rss_url)
    except Exception as e:
        return [TextMessage(text=f"新聞抓取失敗：{e}")]

    if not feed.entries:
        return [TextMessage(text="目前沒有抓到新聞。")]

    lines = ["今日新聞摘要："]
    for i, entry in enumerate(feed.entries[:5], 1):
        title = getattr(entry, "title", "無標題")
        link = getattr(entry, "link", "")
        lines.append(f"{i}. {title}\n{link}")

    return [TextMessage(text="\n\n".join(lines))]
