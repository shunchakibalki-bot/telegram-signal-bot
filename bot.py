import os
import time
import threading
import requests
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer

# ============================================================
# CONFIG
# ============================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
TWELVE_API_KEY = os.getenv("TWELVE_API_KEY")
ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is missing")

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# XAU/USD symbol used by Twelve Data
XAU_SYMBOL = "XAU/USD"

REQUEST_TIMEOUT = 25


# ============================================================
# TELEGRAM API
# ============================================================

def telegram_call(method, params=None):

    try:
        response = requests.post(
            f"{TELEGRAM_API}/{method}",
            data=params or {},
            timeout=REQUEST_TIMEOUT
        )

        if not response.ok:
            print(
                "Telegram error:",
                response.status_code,
                response.text[:500]
            )
            return None

        return response.json()

    except Exception as e:

        print(
            "Telegram request error:",
            repr(e)
        )

        return None


def send_message(chat_id, text):

    return telegram_call(
        "sendMessage",
        {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML"
        }
    )


# ============================================================
# TELEGRAM KEYBOARD
# ============================================================

def main_keyboard():

    return {
        "keyboard": [
            [
                {
                    "text": "🥇 Live Price"
                },
                {
                    "text": "📊 Signal"
                }
            ],
            [
                {
                    "text": "📰 Fundamental"
                },
                {
                    "text": "📅 News"
                }
            ],
            [
                {
                    "text": "🤖 AI Advisor"
                },
                {
                    "text": "📈 Market Analysis"
                }
            ],
            [
                {
                    "text": "⚙️ Settings"
                }
            ]
        ],
        "resize_keyboard": True
    }


def send_main_menu(chat_id):

    try:

        telegram_call(
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": (
                    "🤖 <b>BEGZOD AI XAUUSD</b>\n\n"
                    "🥇 Real-time XAU/USD\n"
                    "📊 Multi-timeframe analysis\n"
                    "📰 Fundamental analysis\n"
                    "📅 Economic news\n"
                    "🤖 AI trading advisor\n\n"
                    "Quyidagi menyudan tanlang:"
                ),
                "parse_mode": "HTML",
                "reply_markup": str(main_keyboard()).replace(
                    "'", '"'
                )
            }
        )

    except Exception as e:

        print(
            "Menu error:",
            repr(e)
        )


# ============================================================
# TWELVE DATA
# ============================================================

def twelve_data(endpoint, params=None):

    if not TWELVE_API_KEY:
        print(
            "TWELVE_API_KEY missing"
        )
        return None

    try:

        request_params = dict(
            params or {}
        )

        request_params["apikey"] = TWELVE_API_KEY

        response = requests.get(
            f"https://api.twelvedata.com/{endpoint}",
            params=request_params,
            timeout=REQUEST_TIMEOUT
        )

        print(
            "TwelveData:",
            endpoint,
            response.status_code
        )

        if not response.ok:
            return None

        data = response.json()

        if data.get("status") == "error":
            print(
                "TwelveData API error:",
                data
            )
            return None

        return data

    except Exception as e:

        print(
            "TwelveData error:",
            repr(e)
        )

        return None


# ============================================================
# REAL-TIME PRICE
# ============================================================

def get_gold_price():

    data = twelve_data(
        "price",
        {
            "symbol": XAU_SYMBOL
        }
    )

    if not data:
        return None

    try:

        return float(
            data["price"]
        )

    except Exception:

        return None


# ============================================================
# TIME SERIES
# ============================================================

def get_candles(interval, outputsize=100):

    data = twelve_data(
        "time_series",
        {
            "symbol": XAU_SYMBOL,
            "interval": interval,
            "outputsize": outputsize,
            "format": "JSON"
        }
    )

    if not data:
        return []

    values = data.get(
        "values",
        []
    )

    candles = []

    for item in reversed(values):

        try:

            candles.append(
                {
                    "time": item.get(
                        "datetime"
                    ),
                    "open": float(
                        item["open"]
                    ),
                    "high": float(
                        item["high"]
                    ),
                    "low": float(
                        item["low"]
                    ),
                    "close": float(
                        item["close"]
                    ),
                    "volume": float(
                        item.get(
                            "volume",
                            0
                        ) or 0
                    )
                }
            )

        except Exception:

            continue

    return candles


# ============================================================
# EMA
# ============================================================

def ema(values, period):

    if len(values) < period:
        return None

    multiplier = 2 / (
        period + 1
    )

    result = sum(
        values[:period]
    ) / period

    for price in values[period:]:

        result = (
            price - result
        ) * multiplier + result

    return result


# ============================================================
# RSI
# ============================================================

def calculate_rsi(values, period=14):

    if len(values) < period + 1:
        return 50.0

    gains = []
    losses = []

    for i in range(
        1,
        len(values)
    ):

        change = (
            values[i] -
            values[i - 1]
        )

        gains.append(
            max(change, 0)
        )

        losses.append(
            max(-change, 0)
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
                avg_gain *
                (period - 1)
            ) +
            gains[i]
        ) / period

        avg_loss = (
            (
                avg_loss *
                (period - 1)
            ) +
            losses[i]
        ) / period

    if avg_loss == 0:
        return 100.0

    rs = (
        avg_gain /
        avg_loss
    )

    return (
        100 -
        (
            100 /
            (1 + rs)
        )
    )


# ============================================================
# ATR
# ============================================================

def calculate_atr(
    candles,
    period=14
):

    if len(candles) < period + 1:
        return 3.0

    trs = []

    for i in range(
        1,
        len(candles)
    ):

        high = candles[i]["high"]
        low = candles[i]["low"]
        previous_close = candles[
            i - 1
        ]["close"]

        tr = max(
            high - low,
            abs(
                high -
                previous_close
            ),
            abs(
                low -
                previous_close
            )
        )

        trs.append(tr)

    return (
        sum(trs[-period:]) /
        period
    )


# ============================================================
# TECHNICAL ANALYSIS
# ============================================================

def timeframe_analysis(
    interval
):

    candles = get_candles(
        interval,
        100
    )

    if len(candles) < 60:
        return None

    closes = [
        c["close"]
        for c in candles
    ]

    ema20 = ema(
        closes,
        20
    )

    ema50 = ema(
        closes,
        50
    )

    rsi = calculate_rsi(
        closes,
        14
    )

    last = candles[-1]
    previous = candles[-2]

    bullish = (
        last["close"] >
        last["open"]
    )

    bearish = (
        last["close"] <
        last["open"]
    )

    bullish_break = (
        last["close"] >
        previous["high"]
    )

    bearish_break = (
        last["close"] <
        previous["low"]
    )

    buy_score = 0
    sell_score = 0

    if ema20 and ema50:

        if ema20 > ema50:
            buy_score += 2

        elif ema20 < ema50:
            sell_score += 2

    if 50 < rsi < 70:
        buy_score += 1

    if 30 < rsi < 50:
        sell_score += 1

    if bullish:
        buy_score += 1

    if bearish:
        sell_score += 1

    if bullish_break:
        buy_score += 2

    if bearish_break:
        sell_score += 2

    if buy_score > sell_score:

        trend = "BULLISH"

    elif sell_score > buy_score:

        trend = "BEARISH"

    else:

        trend = "NEUTRAL"

    return {
        "candles": candles,
        "price": closes[-1],
        "ema20": ema20,
        "ema50": ema50,
        "rsi": rsi,
        "trend": trend,
        "buy_score": buy_score,
        "sell_score": sell_score
    }


# ============================================================
# SIGNAL ENGINE
# ============================================================

def generate_signal():

    tf15 = timeframe_analysis(
        "15min"
    )

    tf5 = timeframe_analysis(
        "5min"
    )

    tf1 = timeframe_analysis(
        "1min"
    )

    if not tf15 or not tf5 or not tf1:

        return {
            "signal": "WAIT",
            "reason": "Market data yetarli emas."
        }

    buy_score = 0
    sell_score = 0

    # 15M trend
    if tf15["trend"] == "BULLISH":
        buy_score += 3

    elif tf15["trend"] == "BEARISH":
        sell_score += 3

    # 5M
    if tf5["trend"] == "BULLISH":
        buy_score += 2

    elif tf5["trend"] == "BEARISH":
        sell_score += 2

    # 1M
    if tf1["trend"] == "BULLISH":
        buy_score += 2

    elif tf1["trend"] == "BEARISH":
        sell_score += 2

    # RSI confirmation
    if tf5["rsi"] > 50:
        buy_score += 1

    elif tf5["rsi"] < 50:
        sell_score += 1

    if tf1["rsi"] > 50:
        buy_score += 1

    elif tf1["rsi"] < 50:
        sell_score += 1

    current_price = tf1["price"]

    atr = calculate_atr(
        tf1["candles"]
    )

    # BUY
    if (
        buy_score >= 7 and
        buy_score > sell_score
    ):

        entry = current_price

        sl = (
            entry -
            atr * 1.2
        )

        risk = (
            entry - sl
        )

        return {
            "signal": "BUY",
            "entry": entry,
            "sl": sl,
            "tp1": entry + risk,
            "tp2": entry + risk * 2,
            "tp3": entry + risk * 3,
            "trend15": tf15["trend"],
            "rsi5": tf5["rsi"],
            "rsi1": tf1["rsi"],
            "buy_score": buy_score,
            "sell_score": sell_score
        }

    # SELL
    if (
        sell_score >= 7 and
        sell_score > buy_score
    ):

        entry = current_price

        sl = (
            entry +
            atr * 1.2
        )

        risk = (
            sl - entry
        )

        return {
            "signal": "SELL",
            "entry": entry,
            "sl": sl,
            "tp1": entry - risk,
            "tp2": entry - risk * 2,
            "tp3": entry - risk * 3,
            "trend15": tf15["trend"],
            "rsi5": tf5["rsi"],
            "rsi1": tf1["rsi"],
            "buy_score": buy_score,
            "sell_score": sell_score
        }

    return {
        "signal": "WAIT",
        "price": current_price,
        "trend15": tf15["trend"],
        "rsi5": tf5["rsi"],
        "rsi1": tf1["rsi"],
        "buy_score": buy_score,
        "sell_score": sell_score
    }


# ============================================================
# SIGNAL MESSAGE
# ============================================================

def signal_message():

    result = generate_signal()

    if result["signal"] == "WAIT":

        return (
            "🟡 <b>XAU/USD</b>\n\n"
            "⏳ <b>WAIT</b>\n\n"
            f"💰 Price: "
            f"<b>{result['price']:.2f}</b>\n\n"
            f"📊 15M Trend: "
            f"<b>{result['trend15']}</b>\n"
            f"📊 5M RSI: "
            f"<b>{result['rsi5']:.1f}</b>\n"
            f"📊 1M RSI: "
            f"<b>{result['rsi1']:.1f}</b>\n\n"
            f"🟢 Buy score: "
            f"<b>{result['buy_score']}</b>\n"
            f"🔴 Sell score: "
            f"<b>{result['sell_score']}</b>\n\n"
            "❌ Kuchli entry tasdig'i yo'q."
        )

    emoji = (
        "🟢"
        if result["signal"] == "BUY"
        else "🔴"
    )

    return (
        f"{emoji} <b>XAU/USD "
        f"{result['signal']}</b>\n\n"
        f"🎯 Entry: "
        f"<b>{result['entry']:.2f}</b>\n"
        f"🛑 Stop Loss: "
        f"<b>{result['sl']:.2f}</b>\n\n"
        f"💰 TP1: "
        f"<b>{result['tp1']:.2f}</b>\n"
        f"💰 TP2: "
        f"<b>{result['tp2']:.2f}</b>\n"
        f"💰 TP3: "
        f"<b>{result['tp3']:.2f}</b>\n\n"
        f"📊 15M: "
        f"<b>{result['trend15']}</b>\n"
        f"📊 5M RSI: "
        f"<b>{result['rsi5']:.1f}</b>\n"
        f"📊 1M RSI: "
        f"<b>{result['rsi1']:.1f}</b>\n\n"
        f"🟢 Buy score: "
        f"<b>{result['buy_score']}</b>\n"
        f"🔴 Sell score: "
        f"<b>{result['sell_score']}</b>\n\n"
        "⚠️ Risk managementdan foydalaning."
    )


# ============================================================
# FUNDAMENTAL
# ============================================================

def get_news():

    if not ALPHA_VANTAGE_API_KEY:

        return []

    try:

        response = requests.get(
            "https://www.alphavantage.co/query",
            params={
                "function": "NEWS_SENTIMENT",
                "tickers": "FOREX:USD",
                "limit": 10,
                "apikey":
                    ALPHA_VANTAGE_API_KEY
            },
            timeout=REQUEST_TIMEOUT
        )

        if not response.ok:
            return []

        data = response.json()

        return data.get(
            "feed",
            []
        )

    except Exception as e:

        print(
            "Alpha Vantage error:",
            repr(e)
        )

        return []


def fundamental_message():

    news = get_news()

    if not news:

        return (
            "📰 <b>FUNDAMENTAL</b>\n\n"
            "Hozircha fundamental news "
            "ma'lumoti olinmadi.\n\n"
            "API limiti yoki data source "
            "vaqtincha unavailable bo'lishi mumkin."
        )

    bullish = 0
    bearish = 0

    lines = []

    for item in news[:5]:

        title = item.get(
            "title",
            "News"
        )

        sentiment = item.get(
            "overall_sentiment_label",
            "Neutral"
        )

        if "Bullish" in sentiment:
            bullish += 1

        elif "Bearish" in sentiment:
            bearish += 1

        lines.append(
            f"• {title[:90]}\n"
            f"  Sentiment: {sentiment}"
        )

    if bullish > bearish:
        bias = "🟢 BULLISH"

    elif bearish > bullish:
        bias = "🔴 BEARISH"

    else:
        bias = "🟡 NEUTRAL"

    return (
        "📰 <b>FUNDAMENTAL ANALYSIS</b>\n\n"
        f"Gold/USD news bias: "
        f"<b>{bias}</b>\n\n"
        + "\n\n".join(lines)
        + "\n\n"
        "⚠️ News sentiment texnik signalning "
        "o'rnini bosmaydi."
    )


# ============================================================
# NEWS
# ============================================================

def news_message():

    news = get_news()

    if not news:

        return (
            "📅 <b>NEWS</b>\n\n"
            "Hozircha yangiliklar olinmadi."
        )

    lines = []

    for item in news[:8]:

        title = item.get(
            "title",
            "News"
        )

        source = item.get(
            "source",
            "Unknown"
        )

        lines.append(
            f"📰 <b>{source}</b>\n"
            f"{title[:120]}"
        )

    return (
        "📅 <b>MARKET NEWS</b>\n\n"
        +
        "\n\n".join(lines)
    )


# ============================================================
# AI ADVISOR
# ============================================================

def advisor_message():

    signal = generate_signal()

    price = get_gold_price()

    if signal["signal"] == "BUY":

        verdict = (
            "🟢 BUY setup mavjud.\n"
            "Lekin entryni risk management bilan "
            "tasdiqlash kerak."
        )

    elif signal["signal"] == "SELL":

        verdict = (
            "🔴 SELL setup mavjud.\n"
            "Entrydan oldin confirmation kuting."
        )

    else:

        verdict = (
            "🟡 HOZIRCHA WAIT.\n"
            "Kuchli confirmation mavjud emas."
        )

    fundamental = fundamental_message()

    return (
        "🤖 <b>BEGZOD AI ADVISOR</b>\n\n"
        f"🥇 Price: "
        f"<b>{price:.2f}</b>\n\n"
        f"📊 Technical: "
        f"<b>{signal['signal']}</b>\n\n"
        f"{verdict}\n\n"
        "📰 Fundamental context:\n"
        f"{fundamental[:1200]}\n\n"
        "⚠️ Bu avtomatik texnik/fundamental "
        "tahlil. Moliyaviy maslahat emas."
    )


# ============================================================
# MARKET ANALYSIS
# ============================================================

def market_message():

    tf15 = timeframe_analysis(
        "15min"
    )

    tf5 = timeframe_analysis(
        "5min"
    )

    tf1 = timeframe_analysis(
        "1min"
    )

    if not tf15 or not tf5 or not tf1:

        return (
            "📈 <b>MARKET ANALYSIS</b>\n\n"
            "Market data yetarli emas."
        )

    return (
        "📈 <b>MARKET ANALYSIS</b>\n\n"
        f"🥇 Price: "
        f"<b>{tf1['price']:.2f}</b>\n\n"
        f"15M: <b>{tf15['trend']}</b>\n"
        f"5M: <b>{tf5['trend']}</b>\n"
        f"1M: <b>{tf1['trend']}</b>\n\n"
        f"5M RSI: "
        f"<b>{tf5['rsi']:.1f}</b>\n"
        f"1M RSI: "
        f"<b>{tf1['rsi']:.1f}</b>\n\n"
        f"Buy score: "
        f"<b>{tf15['buy_score'] + tf5['buy_score'] + tf1['buy_score']}</b>\n"
        f"Sell score: "
        f"<b>{tf15['sell_score'] + tf5['sell_score'] + tf1['sell_score']}</b>"
    )


# ============================================================
# SETTINGS
# ============================================================

def settings_message():

    return (
        "⚙️ <b>SETTINGS</b>\n\n"
        "Symbol: XAU/USD\n"
        "Timeframes: 15M / 5M / 1M\n"
        "Risk model: ATR\n"
        "TP model: 1R / 2R / 3R\n\n"
        "Keyingi versiyalarda:\n"
        "• Risk %\n"
        "• Alert settings\n"
        "• News filter\n"
        "• Trading session"
    )


# ============================================================
# UPDATE HANDLER
# ============================================================

def process_update(update):

    print(
        "UPDATE RECEIVED:",
        update
    )

    if "message" not in update:
        return

    message = update["message"]

    chat_id = message["chat"]["id"]

    text = message.get(
        "text",
        ""
    ).strip()

    if text == "/start":

        send_main_menu(
            chat_id
        )

        return

    if text == "/help":

        send_message(
            chat_id,
            (
                "📚 <b>COMMANDS</b>\n\n"
                "/start — Main menu\n"
                "/price — Live price\n"
                "/signal — Technical signal\n"
                "/fundamental — Fundamental\n"
                "/news — News\n"
                "/advisor — AI Advisor\n"
                "/market — Market analysis"
            )
        )

        return

    if text in (
        "/price",
        "🥇 Live Price"
    ):

        price = get_gold_price()

        if price is None:

            send_message(
                chat_id,
                "❌ XAU/USD narxini olishda xato."
            )

        else:

            send_message(
                chat_id,
                (
                    "🥇 <b>XAU/USD</b>\n\n"
                    f"💰 Live Price: "
                    f"<b>{price:.2f}</b>"
                )
            )

        return

    if text in (
        "/signal",
        "📊 Signal"
    ):

        send_message(
            chat_id,
            "🔎 XAU/USD analiz qilinmoqda..."
        )

        try:

            send_message(
                chat_id,
                signal_message()
            )

        except Exception as e:

            print(
                "Signal error:",
                repr(e)
            )

            send_message(
                chat_id,
                "❌ Signal analizida xatolik."
            )

        return

    if text in (
        "/fundamental",
        "📰 Fundamental"
    ):

        send_message(
            chat_id,
            "📰 Fundamental ma'lumotlar olinmoqda..."
        )

        send_message(
            chat_id,
            fundamental_message()
        )

        return

    if text in (
        "/news",
        "📅 News"
    ):

        send_message(
            chat_id,
            "📅 Market news olinmoqda..."
        )

        send_message(
            chat_id,
            news_message()
        )

        return

    if text in (
        "/advisor",
        "🤖 AI Advisor"
    ):

        send_message(
            chat_id,
            "🤖 AI Advisor analiz qilmoqda..."
        )

        try:

            send_message(
                chat_id,
                advisor_message()
            )

        except Exception as e:

            print(
                "Advisor error:",
                repr(e)
            )

            send_message(
                chat_id,
                "❌ Advisor analizida xatolik."
            )

        return

    if text in (
        "/market",
        "📈 Market Analysis"
    ):

        send_message(
            chat_id,
            "📈 Market analiz qilinmoqda..."
        )

        try:

            send_message(
                chat_id,
                market_message()
            )

        except Exception as e:

            print(
                "Market error:",
                repr(e)
            )

            send_message(
                chat_id,
                "❌ Market analysis xatosi."
            )

        return

    if text == "⚙️ Settings":

        send_message(
            chat_id,
            settings_message()
        )

        return

    send_message(
        chat_id,
        (
            "❓ Buyruq topilmadi.\n\n"
            "Pastdagi menyudan foydalaning."
        )
    )


# ============================================================
# WEBHOOK RESET
# ============================================================

def remove_webhook():

    try:

        result = telegram_call(
            "deleteWebhook",
            {
                "drop_pending_updates": "true"
            }
        )

        print(
            "Webhook reset:",
            result
        )

    except Exception as e:

        print(
            "Webhook reset error:",
            repr(e)
        )


# ============================================================
# TELEGRAM POLLING
# ============================================================

def telegram_loop():

    print(
        "TELEGRAM POLLING STARTED"
    )

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

            if not response.ok:

                print(
                    "Polling HTTP error:",
                    response.status_code,
                    response.text[:500]
                )

                time.sleep(5)

                continue

            data = response.json()

            if not data.get("ok"):

                print(
                    "Polling API error:",
                    data
                )

                time.sleep(5)

                continue

            updates = data.get(
                "result",
                []
            )

            for update in updates:

                offset = (
                    update["update_id"] +
                    1
                )

                process_update(
                    update
                )

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

        self.send_response(
            200
        )

        self.send_header(
            "Content-Type",
            "text/plain"
        )

        self.end_headers()

        self.wfile.write(
            b"Begzod AI XAUUSD Bot is running"
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
        f"WEB SERVER RUNNING ON PORT {port}"
    )

    server.serve_forever()


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    print(
        "======================================"
    )

    print(
        "BEGZOD AI XAUUSD"
    )

    print(
        "BOT STARTING"
    )

    print(
        "======================================"
    )

    print(
        "BOT_TOKEN:",
        "OK" if BOT_TOKEN else "MISSING"
    )

    print(
        "TWELVE_API_KEY:",
        "OK" if TWELVE_API_KEY else "MISSING"
    )

    print(
        "ALPHA_VANTAGE_API_KEY:",
        "OK"
        if ALPHA_VANTAGE_API_KEY
        else "MISSING"
    )

    remove_webhook()

    threading.Thread(
        target=start_server,
        daemon=True
    ).start()

    telegram_loop()
  
