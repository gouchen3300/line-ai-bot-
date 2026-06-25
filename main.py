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
    "watch", "watches", "teach", "teaches", "use", "uses"
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
