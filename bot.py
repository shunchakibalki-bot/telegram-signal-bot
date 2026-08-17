import os
import time
import threading
import requests
from http.server import BaseHTTPRequestHandler, HTTPServer

# ============================================================
# SETTINGS
# ============================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
TWELVE_API_KEY = os.getenv("TWELVE_API_KEY")

SYMBOL = "XAU/USD"

TELEGRAM_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
TWELVE_URL = "https://api.twelvedata.com"

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is missing")

if not TWELVE_API_KEY:
    raise RuntimeError("TWELVE_API_KEY is missing")


# ============================================================
# TWELVE DATA REQUEST
# ============================================================

def twelve_request(endpoint, params=None):

    if params is None:
        params = {}

    params["apikey"] = TWELVE_API_KEY

    response = requests.get(
        f"{TWELVE_URL}/{endpoint}",
        params=params,
        timeout=20
    )

    if response.status_code != 200:
        raise RuntimeError(
            f"Twelve Data HTTP {response.status_code}"
        )

    try:
        data = response.json()
    except ValueError:
        raise RuntimeError(
            "Twelve Data returned invalid JSON"
        )

    if "status" in data:
        if data["status"] == "error":
            raise RuntimeError(
                data.get(
                    "message",
                    "Twelve Data API error"
                )
            )

    if "code" in data and "message" in data:
        raise RuntimeError(
            f"{data['code']}: {data['message']}"
        )

    return data


# ============================================================
# REAL-TIME PRICE
# ============================================================

def get_price():

    data = twelve_request(
        "price",
        {
            "symbol": SYMBOL
        }
    )

    if "price" not in data:
        raise RuntimeError(
            f"Price not found: {data}"
        )

    return float(data["price"])


# ============================================================
# CANDLES
# ============================================================

def get_candles(interval, outputsize=100):

    data = twelve_request(
        "time_series",
        {
            "symbol": SYMBOL,
            "interval": interval,
            "outputsize": outputsize,
            "format": "JSON"
        }
    )

    values = data.get("values")

    if not values:
        raise RuntimeError(
            f"No candle data for {interval}"
        )

    candles = []

    # Twelve Data returns newest first.
    # Reverse so oldest -> newest.
    for item in reversed(values):

        try:
            candles.append({
                "datetime": item["datetime"],
                "open": float(item["open"]),
                "high": float(item["high"]),
                "low": float(item["low"]),
                "close": float(item["close"])
            })

        except (KeyError, ValueError):
            continue

    if len(candles) < 30:
        raise RuntimeError(
            f"Not enough {interval} candles"
        )

    return candles


# ============================================================
# EMA
# ============================================================

def ema(values, period):

    if len(values) < period:
        return None

    value = sum(
        values[:period]
    ) / period

    multiplier = 2 / (period + 1)

    for price in values[period:]:

        value = (
            (price - value)
            * multiplier
            + value
        )

    return value


# ============================================================
# RSI
# ============================================================

def rsi(values, period=14):

    if len(values) < period + 1:
        return 50.0

    gains = []
    losses = []

    for i in range(1, len(values)):

        change = (
            values[i]
            - values[i - 1]
        )

        if change >= 0:
            gains.append(change)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(change))

    avg_gain = (
        sum(gains[:period])
        / period
    )

    avg_loss = (
        sum(losses[:period])
        / period
    )

    for i in range(period, len(gains)):

        avg_gain = (
            (
                avg_gain * (period - 1)
            )
            + gains[i]
        ) / period

        avg_loss = (
            (
                avg_loss * (period - 1)
            )
            + losses[i]
        ) / period

    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss

    return 100 - (
        100 / (1 + rs)
    )


# ============================================================
# ATR
# ============================================================

def atr(candles, period=14):

    if len(candles) < period + 1:
        return 3.0

    ranges = []

    for i in range(1, len(candles)):

        high = candles[i]["high"]
        low = candles[i]["low"]
        previous_close = candles[i - 1]["close"]

        tr = max(
            high - low,
            abs(high - previous_close),
            abs(low - previous_close)
        )

        ranges.append(tr)

    return (
        sum(ranges[-period:])
        / period
    )


# ============================================================
# MARKET ANALYSIS
# ============================================================

def analyze_market():

    candles_15m = get_candles(
        "15min",
        100
    )

    candles_5m = get_candles(
        "5min",
        100
    )

    candles_1m = get_candles(
        "1min",
        100
    )

    # --------------------------------------------------------
    # 15M
    # --------------------------------------------------------

    close15 = [
        x["close"]
        for x in candles_15m
    ]

    ema20_15 = ema(
        close15,
        20
    )

    ema50_15 = ema(
        close15,
        50
    )

    if ema20_15 > ema50_15:
        trend = "BULLISH"
    elif ema20_15 < ema50_15:
        trend = "BEARISH"
    else:
        trend = "NEUTRAL"

    # --------------------------------------------------------
    # 5M
    # --------------------------------------------------------

    close5 = [
        x["close"]
        for x in candles_5m
    ]

    ema20_5 = ema(
        close5,
        20
    )

    ema50_5 = ema(
        close5,
        50
    )

    rsi5 = rsi(
        close5,
        14
    )

    last5 = candles_5m[-1]
    previous5 = candles_5m[-2]

    bullish_break = (
        last5["close"]
        > previous5["high"]
    )

    bearish_break = (
        last5["close"]
        < previous5["low"]
    )

    # --------------------------------------------------------
    # 1M
    # --------------------------------------------------------

    close1 = [
        x["close"]
        for x in candles_1m
    ]

    rsi1 = rsi(
        close1,
        14
    )

    last1 = candles_1m[-1]

    bullish_1m = (
        last1["close"]
        > last1["open"]
    )

    bearish_1m = (
        last1["close"]
        < last1["open"]
    )

    # --------------------------------------------------------
    # SCORES
    # --------------------------------------------------------

    buy = 0
    sell = 0

    # 15M trend
    if trend == "BULLISH":
        buy += 3

    elif trend == "BEARISH":
        sell += 3

    # 5M trend
    if ema20_5 > ema50_5:
        buy += 2

    elif ema20_5 < ema50_5:
        sell += 2

    # 5M RSI
    if 50 < rsi5 < 70:
        buy += 1

    elif 30 < rsi5 < 50:
        sell += 1

    # 5M break
    if bullish_break:
        buy += 2

    if bearish_break:
        sell += 2

    # 1M confirmation
    if bullish_1m and rsi1 > 50:
        buy += 1

    if bearish_1m and rsi1 < 50:
        sell += 1

    # --------------------------------------------------------
    # PRICE
    # --------------------------------------------------------

    price = get_price()

    atr5 = atr(
        candles_5m,
        14
    )

    # --------------------------------------------------------
    # BUY
    # --------------------------------------------------------

    if (
        buy >= 7
        and buy > sell + 1
    ):

        entry = price

        risk = atr5 * 1.0

        sl = entry - risk

        tp1 = entry + risk * 1.5
        tp2 = entry + risk * 2.0
        tp3 = entry + risk * 3.0

        confidence = min(
            95,
            55 + buy * 4
        )

        return {
            "signal": "BUY",
            "entry": entry,
            "sl": sl,
            "tp1": tp1,
            "tp2": tp2,
            "tp3": tp3,
            "confidence": confidence,
            "trend": trend,
            "rsi5": rsi5,
            "rsi1": rsi1,
            "buy": buy,
            "sell": sell
        }

    # --------------------------------------------------------
    # SELL
    # --------------------------------------------------------

    if (
        sell >= 7
        and sell > buy + 1
    ):

        entry = price

        risk = atr5 * 1.0

        sl = entry + risk

        tp1 = entry - risk * 1.5
        tp2 = entry - risk * 2.0
        tp3 = entry - risk * 3.0

        confidence = min(
            95,
            55 + sell * 4
        )

        return {
            "signal": "SELL",
            "entry": entry,
            "sl": sl,
            "tp1": tp1,
            "tp2": tp2,
            "tp3": tp3,
            "confidence": confidence,
            "trend": trend,
            "rsi5": rsi5,
            "rsi1": rsi1,
            "buy": buy,
            "sell": sell
        }

    # --------------------------------------------------------
    # WAIT
    # --------------------------------------------------------

    return {
        "signal": "WAIT",
        "entry": price,
        "confidence": 0,
        "trend": trend,
        "rsi5": rsi5,
        "rsi1": rsi1,
        "buy": buy,
        "sell": sell
    }


# ============================================================
# TELEGRAM
# ============================================================

def send_message(chat_id, text):

    try:

        requests.post(
            f"{TELEGRAM_URL}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML"
            },
            timeout=20
        )

    except Exception as e:

        print(
            "Telegram error:",
            repr(e)
        )


# ============================================================
# SIGNAL MESSAGE
# ============================================================

def signal_message():

    data = analyze_market()

    if data["signal"] == "WAIT":

        return (
            "🟡 <b>XAU/USD</b>\n\n"
            "⏳ <b>WAIT</b>\n\n"
            f"💰 Price: "
            f"<b>{data['entry']:.2f}</b>\n\n"
            f"📊 15M Trend: "
            f"<b>{data['trend']}</b>\n"
            f"📊 5M RSI: "
            f"<b>{data['rsi5']:.1f}</b>\n"
            f"📊 1M RSI: "
            f"<b>{data['rsi1']:.1f}</b>\n\n"
            f"🟢 Buy score: "
            f"<b>{data['buy']}</b>\n"
            f"🔴 Sell score: "
            f"<b>{data['sell']}</b>\n\n"
            "❌ Kuchli entry tasdig'i yo'q."
        )

    emoji = (
        "🟢"
        if data["signal"] == "BUY"
        else "🔴"
    )

    return (
        f"{emoji} "
        f"<b>XAU/USD {data['signal']}</b>\n\n"

        f"🎯 Entry: "
        f"<b>{data['entry']:.2f}</b>\n"

        f"🛑 Stop Loss: "
        f"<b>{data['sl']:.2f}</b>\n\n"

        f"💰 TP1: "
        f"<b>{data['tp1']:.2f}</b>\n"

        f"💰 TP2: "
        f"<b>{data['tp2']:.2f}</b>\n"

        f"💰 TP3: "
        f"<b>{data['tp3']:.2f}</b>\n\n"

        f"📊 15M: "
        f"<b>{data['trend']}</b>\n"

        f"📊 5M RSI: "
        f"<b>{data['rsi5']:.1f}</b>\n"

        f"📊 1M RSI: "
        f"<b>{data['rsi1']:.1f}</b>\n\n"

        f"🧠 Confidence: "
        f"<b>{data['confidence']}%</b>\n\n"

        "⚠️ Avtomatik texnik analiz."
    )


# ============================================================
# COMMANDS
# ============================================================

def process_update(update):

    if "message" not in update:
        return

    message = update["message"]

    chat_id = message["chat"]["id"]

    text = message.get(
        "text",
        ""
    ).strip()

    if text == "/start":

        send_message(
            chat_id,
            (
                "🤖 <b>AI XAU/USD Bot</b>\n\n"
                "Real-time XAU/USD data\n"
                "15M + 5M + 1M analysis\n\n"
                "/price — narx\n"
                "/signal — analiz\n"
                "/help — yordam"
            )
        )

    elif text == "/price":

        try:

            price = get_price()

            send_message(
                chat_id,
                (
                    "🥇 <b>XAU/USD</b>\n\n"
                    f"💰 Current price: "
                    f"<b>{price:.2f}</b>\n\n"
                    "📡 Source: Twelve Data"
                )
            )

        except Exception as e:

            send_message(
                chat_id,
                (
                    "❌ Price error:\n"
                    f"<code>{str(e)}</code>"
                )
            )

    elif text == "/signal":

        send_message(
            chat_id,
            "🔎 XAU/USD analiz qilinmoqda..."
        )

        try:

            result = signal_message()

            send_message(
                chat_id,
                result
            )

        except Exception as e:

            print(
                "Analysis error:",
                repr(e)
            )

            send_message(
                chat_id,
                (
                    "❌ <b>Analiz xatosi</b>\n\n"
                    f"<code>{str(e)}</code>"
                )
            )

    elif text == "/help":

        send_message(
            chat_id,
            (
                "📚 <b>Commands</b>\n\n"
                "/price — real-time XAU/USD\n"
                "/signal — Entry / SL / TP\n"
                "/start — botni boshlash"
            )
        )


# ============================================================
# TELEGRAM POLLING
# ============================================================

def telegram_loop():

    offset = None

    while True:

        try:

            params = {
                "timeout": 30
            }

            if offset is not None:
                params["offset"] = offset

            response = requests.get(
                f"{TELEGRAM_URL}/getUpdates",
                params=params,
                timeout=40
            )

            if response.status_code != 200:

                time.sleep(5)
                continue

            data = response.json()

            if not data.get("ok"):

                time.sleep(5)
                continue

            for update in data.get(
                "result",
                []
            ):

                offset = (
                    update["update_id"] + 1
                )

                process_update(update)

        except Exception as e:

            print(
                "Polling error:",
                repr(e)
            )

            time.sleep(5)


# ============================================================
# RENDER SERVER
# ============================================================

class HealthHandler(
    BaseHTTPRequestHandler
):

    def do_GET(self):

        self.send_response(200)

        self.send_header(
            "Content-Type",
            "text/plain"
        )

        self.end_headers()

        self.wfile.write(
            b"AI XAUUSD Bot is running"
        )

    def log_message(
        self,
        format,
        *args
    ):
        return


def start_server():

    port = int(
        os.environ.get(
            "PORT",
            "10000"
        )
    )

    server = HTTPServer(
        ("0.0.0.0", port),
        HealthHandler
    )

    print(
        f"Server running on port {port}"
    )

    server.serve_forever()


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    print(
        "================================"
    )

    print(
        "AI XAU/USD TELEGRAM BOT"
    )

    print(
        "================================"
    )

    threading.Thread(
        target=start_server,
        daemon=True
    ).start()

    telegram_loop()
  
