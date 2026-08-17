import os
import time
import threading
import requests
from http.server import BaseHTTPRequestHandler, HTTPServer

# ============================================================
# CONFIG
# ============================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is missing")

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

SYMBOL = "GC=F"
INTERVAL = "5m"
RANGE = "5d"

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json,text/plain,*/*",
}

# ============================================================
# TELEGRAM
# ============================================================

def send_message(chat_id, text):
    try:
        response = requests.post(
            f"{TELEGRAM_API}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML"
            },
            timeout=20
        )

        if not response.ok:
            print(
                "Telegram send error:",
                response.status_code,
                response.text[:300]
            )

    except Exception as e:
        print("Telegram request error:", repr(e))


# ============================================================
# MARKET DATA
# ============================================================

def fetch_yahoo(url):

    response = requests.get(
        url,
        headers=HEADERS,
        timeout=20
    )

    print(
        "Yahoo response:",
        response.status_code,
        response.headers.get("content-type")
    )

    if response.status_code != 200:
        raise RuntimeError(
            f"Yahoo HTTP {response.status_code}"
        )

    body = response.text.strip()

    if not body:
        raise RuntimeError(
            "Yahoo returned an empty response"
        )

    try:
        return response.json()

    except ValueError:
        raise RuntimeError(
            "Yahoo returned invalid JSON"
        )


def get_gold_data():

    urls = [
        (
            "https://query1.finance.yahoo.com/v8/finance/chart/"
            f"{SYMBOL}?interval={INTERVAL}&range={RANGE}"
        ),
        (
            "https://query2.finance.yahoo.com/v8/finance/chart/"
            f"{SYMBOL}?interval={INTERVAL}&range={RANGE}"
        )
    ]

    last_error = None

    for url in urls:

        try:

            data = fetch_yahoo(url)

            chart = data.get("chart")

            if not chart:
                raise RuntimeError(
                    "Yahoo response has no chart object"
                )

            if chart.get("error"):
                raise RuntimeError(
                    f"Yahoo API error: {chart['error']}"
                )

            results = chart.get("result")

            if not results:
                raise RuntimeError(
                    "Yahoo returned no result"
                )

            result = results[0]

            timestamps = result.get("timestamp")

            indicators = result.get(
                "indicators",
                {}
            )

            quote_list = indicators.get(
                "quote",
                []
            )

            if not timestamps or not quote_list:
                raise RuntimeError(
                    "Yahoo returned no candle data"
                )

            quote = quote_list[0]

            opens = quote.get("open", [])
            highs = quote.get("high", [])
            lows = quote.get("low", [])
            closes = quote.get("close", [])
            volumes = quote.get("volume", [])

            candles = []

            length = min(
                len(timestamps),
                len(opens),
                len(highs),
                len(lows),
                len(closes)
            )

            for i in range(length):

                try:

                    if (
                        opens[i] is None
                        or highs[i] is None
                        or lows[i] is None
                        or closes[i] is None
                    ):
                        continue

                    volume = 0

                    if (
                        i < len(volumes)
                        and volumes[i] is not None
                    ):
                        volume = float(
                            volumes[i]
                        )

                    candles.append({
                        "time": timestamps[i],
                        "open": float(opens[i]),
                        "high": float(highs[i]),
                        "low": float(lows[i]),
                        "close": float(closes[i]),
                        "volume": volume
                    })

                except (
                    TypeError,
                    ValueError,
                    IndexError
                ):
                    continue

            if len(candles) < 60:
                raise RuntimeError(
                    f"Not enough candles: {len(candles)}"
                )

            print(
                f"Market data OK: "
                f"{len(candles)} candles"
            )

            return candles

        except Exception as e:

            print(
                "Market endpoint failed:",
                repr(e)
            )

            last_error = e

    raise RuntimeError(
        f"XAUUSD data unavailable: {last_error}"
    )


# ============================================================
# EMA
# ============================================================

def ema(values, period):

    if len(values) < period:
        return None

    result = sum(
        values[:period]
    ) / period

    multiplier = 2 / (
        period + 1
    )

    for price in values[period:]:

        result = (
            (price - result)
            * multiplier
            + result
        )

    return result


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

        if change > 0:

            gains.append(change)
            losses.append(0.0)

        else:

            gains.append(0.0)
            losses.append(
                abs(change)
            )

    avg_gain = (
        sum(gains[:period])
        / period
    )

    avg_loss = (
        sum(losses[:period])
        / period
    )

    for i in range(
        period,
        len(gains)
    ):

        avg_gain = (
            (
                avg_gain
                * (period - 1)
            )
            + gains[i]
        ) / period

        avg_loss = (
            (
                avg_loss
                * (period - 1)
            )
            + losses[i]
        ) / period

    if avg_loss == 0:
        return 100.0

    rs = (
        avg_gain
        / avg_loss
    )

    return (
        100
        - (
            100
            / (1 + rs)
        )
    )


# ============================================================
# ATR
# ============================================================

def atr(candles, period=14):

    if len(candles) < period + 1:
        return 3.0

    ranges = []

    for i in range(
        1,
        len(candles)
    ):

        high = candles[i]["high"]
        low = candles[i]["low"]

        previous_close = (
            candles[i - 1]["close"]
        )

        true_range = max(
            high - low,
            abs(
                high
                - previous_close
            ),
            abs(
                low
                - previous_close
            )
        )

        ranges.append(
            true_range
        )

    return (
        sum(
            ranges[-period:]
        )
        / period
    )


# ============================================================
# MARKET STRUCTURE
# ============================================================

def structure_score(candles):

    if len(candles) < 10:
        return 0, 0

    recent = candles[-6:]

    previous_high = max(
        c["high"]
        for c in candles[-10:-2]
    )

    previous_low = min(
        c["low"]
        for c in candles[-10:-2]
    )

    last = recent[-1]

    buy = 0
    sell = 0

    if last["close"] > previous_high:
        buy += 2

    if last["close"] < previous_low:
        sell += 2

    return buy, sell


# ============================================================
# SIGNAL ENGINE
# ============================================================

def generate_signal():

    candles = get_gold_data()

    closes = [
        c["close"]
        for c in candles
    ]

    price = closes[-1]

    ema20 = ema(
        closes,
        20
    )

    ema50 = ema(
        closes,
        50
    )

    current_rsi = rsi(
        closes,
        14
    )

    current_atr = atr(
        candles,
        14
    )

    last = candles[-1]

    previous = candles[-2]

    buy_score = 0
    sell_score = 0

    # --------------------------------------------------------
    # TREND
    # --------------------------------------------------------

    if ema20 > ema50:
        buy_score += 2

    elif ema20 < ema50:
        sell_score += 2

    # --------------------------------------------------------
    # RSI
    # --------------------------------------------------------

    if 52 <= current_rsi <= 68:
        buy_score += 1

    elif 32 <= current_rsi <= 48:
        sell_score += 1

    # --------------------------------------------------------
    # CANDLE MOMENTUM
    # --------------------------------------------------------

    if last["close"] > last["open"]:
        buy_score += 1

    elif last["close"] < last["open"]:
        sell_score += 1

    # --------------------------------------------------------
    # BREAKOUT
    # --------------------------------------------------------

    if last["close"] > previous["high"]:
        buy_score += 2

    elif last["close"] < previous["low"]:
        sell_score += 2

    # --------------------------------------------------------
    # STRUCTURE
    # --------------------------------------------------------

    structure_buy, structure_sell = (
        structure_score(candles)
    )

    buy_score += structure_buy
    sell_score += structure_sell

    # --------------------------------------------------------
    # NO TRADE
    # --------------------------------------------------------

    if (
        buy_score < 5
        and sell_score < 5
    ):

        return "WAIT", {
            "entry": price,
            "rsi": current_rsi,
            "ema20": ema20,
            "ema50": ema50,
            "atr": current_atr,
            "buy_score": buy_score,
            "sell_score": sell_score
        }

    # --------------------------------------------------------
    # BUY
    # --------------------------------------------------------

    if (
        buy_score >= 5
        and buy_score > sell_score
    ):

        entry = price

        risk = current_atr * 1.2

        sl = (
            entry - risk
        )

        tp1 = (
            entry + risk
        )

        tp2 = (
            entry + risk * 2
        )

        tp3 = (
            entry + risk * 3
        )

        confidence = min(
            95,
            50
            + buy_score * 5
        )

        return "BUY", {
            "entry": entry,
            "sl": sl,
            "tp1": tp1,
            "tp2": tp2,
            "tp3": tp3,
            "rsi": current_rsi,
            "ema20": ema20,
            "ema50": ema50,
            "atr": current_atr,
            "score": buy_score,
            "confidence": confidence
        }

    # --------------------------------------------------------
    # SELL
    # --------------------------------------------------------

    if (
        sell_score >= 5
        and sell_score > buy_score
    ):

        entry = price

        risk = current_atr * 1.2

        sl = (
            entry + risk
        )

        tp1 = (
            entry - risk
        )

        tp2 = (
            entry - risk * 2
        )

        tp3 = (
            entry - risk * 3
        )

        confidence = min(
            95,
            50
            + sell_score * 5
        )

        return "SELL", {
            "entry": entry,
            "sl": sl,
            "tp1": tp1,
            "tp2": tp2,
            "tp3": tp3,
            "rsi": current_rsi,
            "ema20": ema20,
            "ema50": ema50,
            "atr": current_atr,
            "score": sell_score,
            "confidence": confidence
        }

    return "WAIT", {
        "entry": price,
        "rsi": current_rsi,
        "ema20": ema20,
        "ema50": ema50,
        "atr": current_atr,
        "buy_score": buy_score,
        "sell_score": sell_score
    }


# ============================================================
# FORMAT SIGNAL
# ============================================================

def create_signal_message():

    signal, data = (
        generate_signal()
    )

    if signal == "WAIT":

        return (
            "🟡 <b>XAUUSD SIGNAL</b>\n\n"
            "⏳ <b>WAIT</b>\n\n"
            f"💰 Price: "
            f"<b>{data['entry']:.2f}</b>\n"
            f"📊 RSI: "
            f"<b>{data['rsi']:.1f}</b>\n"
            f"📈 EMA20: "
            f"<b>{data['ema20']:.2f}</b>\n"
            f"📉 EMA50: "
            f"<b>{data['ema50']:.2f}</b>\n"
            f"🔥 Buy score: "
            f"<b>{data['buy_score']}</b>\n"
            f"🔥 Sell score: "
            f"<b>{data['sell_score']}</b>\n\n"
            "Bozor sharoiti aniq emas."
        )

    if signal == "BUY":
        emoji = "🟢"
    else:
        emoji = "🔴"

    return (
        f"{emoji} "
        f"<b>XAUUSD {signal}</b>\n\n"

        f"🎯 Entry: "
        f"<b>{data['entry']:.2f}</b>\n"

        f"🛑 SL: "
        f"<b>{data['sl']:.2f}</b>\n\n"

        f"💰 TP1: "
        f"<b>{data['tp1']:.2f}</b>\n"

        f"💰 TP2: "
        f"<b>{data['tp2']:.2f}</b>\n"

        f"💰 TP3: "
        f"<b>{data['tp3']:.2f}</b>\n\n"

        f"📊 RSI: "
        f"<b>{data['rsi']:.1f}</b>\n"

        f"📈 EMA20: "
        f"<b>{data['ema20']:.2f}</b>\n"

        f"📉 EMA50: "
        f"<b>{data['ema50']:.2f}</b>\n"

        f"🔥 Score: "
        f"<b>{data['score']}</b>\n"

        f"🧠 Confidence: "
        f"<b>{data['confidence']}%</b>\n\n"

        "⚠️ Bu signal avtomatik texnik "
        "analiz asosida ishlab chiqildi."
    )


# ============================================================
# COMMAND PROCESSOR
# ============================================================

def process_update(update):

    if "message" not in update:
        return

    message = update["message"]

    chat_id = (
        message["chat"]["id"]
    )

    text = message.get(
        "text",
        ""
    ).strip()

    # START
    if text == "/start":

        send_message(
            chat_id,
            (
                "🤖 <b>AI XAUUSD "
                "Signal Bot</b>\n\n"

                "✅ Bot online.\n\n"

                "📌 /signal — XAUUSD "
                "analiz\n"

                "📌 /price — joriy narx\n"

                "📌 /help — yordam"
            )
        )

    # SIGNAL
    elif text == "/signal":

        send_message(
            chat_id,
            "🔎 XAUUSD analiz qilinmoqda..."
        )

        try:

            result = (
                create_signal_message()
            )

            send_message(
                chat_id,
                result
            )

        except Exception as e:

            print(
                "Signal error:",
                repr(e)
            )

            send_message(
                chat_id,
                (
                    "❌ <b>Analiz xatosi</b>\n\n"
                    f"<code>{str(e)}</code>"
                )
            )

    # PRICE
    elif text == "/price":

        try:

            candles = (
                get_gold_data()
            )

            if not candles:
                raise RuntimeError(
                    "No market data"
                )

            price = (
                candles[-1]["close"]
            )

            send_message(
                chat_id,
                (
                    "🥇 <b>XAUUSD</b>\n\n"
                    f"💰 Current price: "
                    f"<b>{price:.2f}</b>"
                )
            )

        except Exception as e:

            print(
                "Price error:",
                repr(e)
            )

            send_message(
                chat_id,
                (
                    "❌ <b>Price error</b>\n\n"
                    f"<code>{str(e)}</code>"
                )
            )

    # HELP
    elif text == "/help":

        send_message(
            chat_id,
            (
                "📚 <b>Commands</b>\n\n"
                "/start — Botni boshlash\n"
                "/signal — XAUUSD signal\n"
                "/price — narx\n"
                "/help — yordam"
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
                f"{TELEGRAM_API}/getUpdates",
                params=params,
                timeout=40
            )

            if response.status_code != 200:

                print(
                    "Telegram HTTP:",
                    response.status_code
                )

                time.sleep(5)
                continue

            try:

                data = (
                    response.json()
                )

            except ValueError:

                print(
                    "Telegram returned "
                    "invalid JSON"
                )

                time.sleep(5)
                continue

            if not data.get("ok"):

                print(
                    "Telegram API error:",
                    data
                )

                time.sleep(5)
                continue

            for update in data.get(
                "result",
                []
            ):

                offset = (
                    update["update_id"]
                    + 1
                )

                try:

                    process_update(
                        update
                    )

                except Exception as e:

                    print(
                        "Update error:",
                        repr(e)
                    )

        except requests.RequestException as e:

            print(
                "Telegram network error:",
                repr(e)
            )

            time.sleep(5)

        except Exception as e:

            print(
                "Polling error:",
                repr(e)
            )

            time.sleep(5)


# ============================================================
# RENDER HEALTH SERVER
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
            b"XAUUSD Telegram Signal Bot is running"
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
        (
            "0.0.0.0",
            port
        ),
        HealthHandler
    )

    print(
        f"Health server running "
        f"on port {port}"
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
        "XAUUSD TELEGRAM SIGNAL BOT"
    )

    print(
        "================================"
    )

    threading.Thread(
        target=start_server,
        daemon=True
    ).start()

    telegram_loop()
  
