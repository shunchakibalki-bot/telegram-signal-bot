import os
import time
import threading
import requests
from http.server import BaseHTTPRequestHandler, HTTPServer

# ==============================
# SETTINGS
# ==============================

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable not found")

TELEGRAM_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

SYMBOL = "GC=F"       # Gold Futures = XAUUSD proxy
INTERVAL = "5m"
RANGE = "5d"


# ==============================
# TELEGRAM
# ==============================

def send_message(chat_id, text):
    try:
        requests.post(
            f"{TELEGRAM_URL}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML"
            },
            timeout=15
        )
    except Exception as e:
        print("Telegram error:", e)


# ==============================
# MARKET DATA
# ==============================

def get_gold_data():
    url = (
        "https://query1.finance.yahoo.com/v8/finance/chart/"
        f"{SYMBOL}?interval={INTERVAL}&range={RANGE}"
    )

    r = requests.get(url, timeout=20)
    data = r.json()

    result = data["chart"]["result"][0]

    timestamps = result["timestamp"]
    quote = result["indicators"]["quote"][0]

    candles = []

    for i in range(len(timestamps)):
        try:
            candles.append({
                "time": timestamps[i],
                "open": float(quote["open"][i]),
                "high": float(quote["high"][i]),
                "low": float(quote["low"][i]),
                "close": float(quote["close"][i]),
                "volume": float(quote["volume"][i] or 0)
            })
        except:
            pass

    return candles


# ==============================
# INDICATORS
# ==============================

def ema(values, period):
    if len(values) < period:
        return None

    multiplier = 2 / (period + 1)

    result = sum(values[:period]) / period

    for price in values[period:]:
        result = (price - result) * multiplier + result

    return result


def rsi(values, period=14):
    if len(values) < period + 1:
        return 50

    gains = []
    losses = []

    for i in range(1, len(values)):
        change = values[i] - values[i - 1]

        if change > 0:
            gains.append(change)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(change))

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    for i in range(period, len(gains)):
        avg_gain = ((avg_gain * (period - 1)) + gains[i]) / period
        avg_loss = ((avg_loss * (period - 1)) + losses[i]) / period

    if avg_loss == 0:
        return 100

    rs = avg_gain / avg_loss

    return 100 - (100 / (1 + rs))


def atr(candles, period=14):
    if len(candles) < period + 1:
        return 3.0

    true_ranges = []

    for i in range(1, len(candles)):
        high = candles[i]["high"]
        low = candles[i]["low"]
        previous_close = candles[i - 1]["close"]

        tr = max(
            high - low,
            abs(high - previous_close),
            abs(low - previous_close)
        )

        true_ranges.append(tr)

    return sum(true_ranges[-period:]) / period


# ==============================
# SIGNAL ENGINE
# ==============================

def generate_signal():
    candles = get_gold_data()

    if len(candles) < 60:
        return "WAIT", None

    closes = [c["close"] for c in candles]

    price = closes[-1]

    ema20 = ema(closes, 20)
    ema50 = ema(closes, 50)

    current_rsi = rsi(closes, 14)

    current_atr = atr(candles, 14)

    last = candles[-1]
    previous = candles[-2]

    bullish_candle = last["close"] > last["open"]
    bearish_candle = last["close"] < last["open"]

    bullish_break = last["close"] > previous["high"]
    bearish_break = last["close"] < previous["low"]

    score_buy = 0
    score_sell = 0

    # TREND
    if ema20 > ema50:
        score_buy += 2

    if ema20 < ema50:
        score_sell += 2

    # RSI
    if 50 < current_rsi < 70:
        score_buy += 1

    if 30 < current_rsi < 50:
        score_sell += 1

    # MOMENTUM
    if bullish_candle:
        score_buy += 1

    if bearish_candle:
        score_sell += 1

    # BREAKOUT
    if bullish_break:
        score_buy += 2

    if bearish_break:
        score_sell += 2

    # ==========================
    # BUY
    # ==========================

    if score_buy >= 5 and score_buy > score_sell:

        entry = price

        stop_loss = entry - (current_atr * 1.2)

        risk = entry - stop_loss

        take_profit_1 = entry + risk
        take_profit_2 = entry + (risk * 2)
        take_profit_3 = entry + (risk * 3)

        return "BUY", {
            "entry": entry,
            "sl": stop_loss,
            "tp1": take_profit_1,
            "tp2": take_profit_2,
            "tp3": take_profit_3,
            "rsi": current_rsi,
            "ema20": ema20,
            "ema50": ema50,
            "score": score_buy
        }

    # ==========================
    # SELL
    # ==========================

    if score_sell >= 5 and score_sell > score_buy:

        entry = price

        stop_loss = entry + (current_atr * 1.2)

        risk = stop_loss - entry

        take_profit_1 = entry - risk
        take_profit_2 = entry - (risk * 2)
        take_profit_3 = entry - (risk * 3)

        return "SELL", {
            "entry": entry,
            "sl": stop_loss,
            "tp1": take_profit_1,
            "tp2": take_profit_2,
            "tp3": take_profit_3,
            "rsi": current_rsi,
            "ema20": ema20,
            "ema50": ema50,
            "score": score_sell
        }

    return "WAIT", {
        "entry": price,
        "rsi": current_rsi,
        "ema20": ema20,
        "ema50": ema50,
        "score": max(score_buy, score_sell)
    }


# ==============================
# SIGNAL MESSAGE
# ==============================

def signal_message():

    signal, data = generate_signal()

    if data is None:
        return "⚠️ Ma'lumot olishda xatolik."

    if signal == "WAIT":

        return (
            "🟡 <b>XAUUSD SIGNAL</b>\n\n"
            "⏳ <b>WAIT</b>\n\n"
            f"💰 Price: <b>{data['entry']:.2f}</b>\n"
            f"📊 RSI: <b>{data['rsi']:.1f}</b>\n"
            f"📈 EMA20: <b>{data['ema20']:.2f}</b>\n"
            f"📉 EMA50: <b>{data['ema50']:.2f}</b>\n\n"
            "Bozor sharoiti aniq emas."
        )

    emoji = "🟢" if signal == "BUY" else "🔴"

    return (
        f"{emoji} <b>XAUUSD {signal}</b>\n\n"
        f"🎯 Entry: <b>{data['entry']:.2f}</b>\n"
        f"🛑 Stop Loss: <b>{data['sl']:.2f}</b>\n\n"
        f"💰 TP1: <b>{data['tp1']:.2f}</b>\n"
        f"💰 TP2: <b>{data['tp2']:.2f}</b>\n"
        f"💰 TP3: <b>{data['tp3']:.2f}</b>\n\n"
        f"📊 RSI: <b>{data['rsi']:.1f}</b>\n"
        f"📈 EMA20: <b>{data['ema20']:.2f}</b>\n"
        f"📉 EMA50: <b>{data['ema50']:.2f}</b>\n"
        f"🔥 Signal Score: <b>{data['score']}/6+</b>\n\n"
        "⚠️ Risk managementdan foydalaning."
    )


# ==============================
# TELEGRAM COMMANDS
# ==============================

def process_update(update):

    if "message" not in update:
        return

    message = update["message"]

    chat_id = message["chat"]["id"]

    text = message.get("text", "").strip()

    if text == "/start":

        send_message(
            chat_id,
            "🤖 <b>XAUUSD AI Signal Bot</b>\n\n"
            "Bot ishga tushdi.\n\n"
            "📌 /signal — XAUUSD signal\n"
            "📌 /price — joriy narx\n"
            "📌 /help — yordam"
        )

    elif text == "/signal":

        send_message(
            chat_id,
            "🔎 XAUUSD analiz qilinmoqda..."
        )

        try:
            result = signal_message()
            send_message(chat_id, result)

        except Exception as e:

            send_message(
                chat_id,
                f"❌ Analiz xatosi:\n{str(e)}"
            )

    elif text == "/price":

        try:

            candles = get_gold_data()

            price = candles[-1]["close"]

            send_message(
                chat_id,
                f"🥇 <b>XAUUSD</b>\n\n"
                f"💰 Current price: <b>{price:.2f}</b>"
            )

        except Exception as e:

            send_message(
                chat_id,
                f"❌ Price error: {str(e)}"
            )

    elif text == "/help":

        send_message(
            chat_id,
            "📚 <b>Commands</b>\n\n"
            "/start — Botni boshlash\n"
            "/signal — XAUUSD analiz\n"
            "/price — XAUUSD narxi\n"
            "/help — Yordam"
        )


# ==============================
# TELEGRAM POLLING
# ==============================

def telegram_loop():

    offset = None

    while True:

        try:

            response = requests.get(
                f"{TELEGRAM_URL}/getUpdates",
                params={
                    "timeout": 30,
                    "offset": offset
                },
                timeout=40
            )

            data = response.json()

            if not data.get("ok"):
                time.sleep(5)
                continue

            for update in data["result"]:

                offset = update["update_id"] + 1

                process_update(update)

        except Exception as e:

            print("Polling error:", e)

            time.sleep(5)


# ==============================
# RENDER WEB SERVER
# ==============================

class HealthHandler(BaseHTTPRequestHandler):

    def do_GET(self):

        self.send_response(200)

        self.send_header(
            "Content-Type",
            "text/plain"
        )

        self.end_headers()

        self.wfile.write(
            b"XAUUSD Telegram Signal Bot is running!"
        )

    def log_message(self, format, *args):
        return


def start_server():

    port = int(
        os.environ.get("PORT", 10000)
    )

    server = HTTPServer(
        ("0.0.0.0", port),
        HealthHandler
    )

    print(
        f"Web server running on port {port}"
    )

    server.serve_forever()


# ==============================
# START BOT
# ==============================

if __name__ == "__main__":

    print("==============================")
    print("XAUUSD TELEGRAM SIGNAL BOT")
    print("==============================")

    threading.Thread(
        target=start_server,
        daemon=True
    ).start()

    telegram_loop()
  
