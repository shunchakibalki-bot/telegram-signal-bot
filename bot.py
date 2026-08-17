import os
import time
import json
import threading
import requests

from http.server import BaseHTTPRequestHandler, HTTPServer


# ============================================================
# CONFIG
# ============================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
TWELVE_API_KEY = os.getenv("TWELVE_API_KEY")
ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY")

TELEGRAM_API = (
    f"https://api.telegram.org/bot{BOT_TOKEN}"
    if BOT_TOKEN
    else ""
)

XAU_SYMBOL = "XAU/USD"

TIMEOUT = 25


# ============================================================
# STARTUP CHECK
# ============================================================

print("======================================")
print("BEGZOD AI XAUUSD BOT")
print("======================================")

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
    "OK" if ALPHA_VANTAGE_API_KEY else "MISSING"
)


# ============================================================
# TELEGRAM
# ============================================================

def telegram_request(
    method,
    data=None
):

    if not BOT_TOKEN:
        print("BOT_TOKEN missing")
        return None

    try:

        response = requests.post(
            f"{TELEGRAM_API}/{method}",
            data=data or {},
            timeout=TIMEOUT
        )

        print(
            "Telegram:",
            method,
            response.status_code
        )

        if not response.ok:

            print(
                response.text[:500]
            )

            return None

        result = response.json()

        if not result.get("ok"):

            print(
                "Telegram API error:",
                result
            )

            return None

        return result

    except Exception as e:

        print(
            "Telegram request error:",
            repr(e)
        )

        return None


def send_message(
    chat_id,
    text,
    keyboard=None
):

    data = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }

    if keyboard is not None:

        data["reply_markup"] = json.dumps(
            keyboard,
            ensure_ascii=False
        )

    return telegram_request(
        "sendMessage",
        data
    )


# ============================================================
# MAIN MENU
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
        "resize_keyboard": True,
        "one_time_keyboard": False
    }


def send_main_menu(
    chat_id
):

    text = (
        "🤖 <b>BEGZOD AI XAUUSD</b>\n\n"
        "🥇 Real-time XAU/USD\n"
        "📊 15M + 5M + 1M analysis\n"
        "📰 Fundamental analysis\n"
        "📅 Market news\n"
        "🤖 AI Advisor\n\n"
        "👇 Kerakli bo‘limni tanlang:"
    )

    send_message(
        chat_id,
        text,
        main_keyboard()
    )


# ============================================================
# TWELVE DATA
# ============================================================

def twelve_request(
    endpoint,
    params=None
):

    if not TWELVE_API_KEY:

        print(
            "TWELVE_API_KEY missing"
        )

        return None

    try:

        request_params = dict(
            params or {}
        )

        request_params[
            "apikey"
        ] = TWELVE_API_KEY

        response = requests.get(
            f"https://api.twelvedata.com/{endpoint}",
            params=request_params,
            timeout=TIMEOUT
        )

        print(
            "Twelve Data:",
            endpoint,
            response.status_code
        )

        if not response.ok:

            print(
                response.text[:500]
            )

            return None

        data = response.json()

        if data.get("status") == "error":

            print(
                "Twelve Data API error:",
                data
            )

            return None

        return data

    except Exception as e:

        print(
            "Twelve Data error:",
            repr(e)
        )

        return None


# ============================================================
# LIVE XAU/USD PRICE
# ============================================================

def get_gold_price():

    data = twelve_request(
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

    except Exception as e:

        print(
            "Price parse error:",
            repr(e)
        )

        return None


# ============================================================
# CANDLES
# ============================================================

def get_candles(
    interval,
    outputsize=100
):

    data = twelve_request(
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
                        "datetime",
                        ""
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

def calculate_ema(
    values,
    period
):

    if len(values) < period:

        return None

    multiplier = (
        2 /
        (period + 1)
    )

    result = (
        sum(
            values[:period]
        ) /
        period
    )

    for value in values[period:]:

        result = (
            (
                value -
                result
            ) *
            multiplier
        ) + result

    return result


# ============================================================
# RSI
# ============================================================

def calculate_rsi(
    values,
    period=14
):

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

        if change > 0:

            gains.append(
                change
            )

            losses.append(0)

        else:

            gains.append(0)

            losses.append(
                abs(change)
            )

    avg_gain = (
        sum(
            gains[:period]
        ) /
        period
    )

    avg_loss = (
        sum(
            losses[:period]
        ) /
        period
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

    ranges = []

    for i in range(
        1,
        len(candles)
    ):

        high = candles[i]["high"]

        low = candles[i]["low"]

        previous_close = candles[
            i - 1
        ]["close"]

        true_range = max(
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

        ranges.append(
            true_range
        )

    return (
        sum(
            ranges[-period:]
        ) /
        period
    )


# ============================================================
# TIMEFRAME ANALYSIS
# ============================================================

def analyze_timeframe(
    interval
):

    candles = get_candles(
        interval,
        100
    )

    if len(candles) < 60:

        return None

    closes = [
        candle["close"]
        for candle in candles
    ]

    ema20 = calculate_ema(
        closes,
        20
    )

    ema50 = calculate_ema(
        closes,
        50
    )

    rsi = calculate_rsi(
        closes,
        14
    )

    last = candles[-1]

    previous = candles[-2]

    buy_score = 0

    sell_score = 0

    # Trend
    if ema20 is not None and ema50 is not None:

        if ema20 > ema50:

            buy_score += 2

        elif ema20 < ema50:

            sell_score += 2

    # RSI
    if 50 < rsi < 70:

        buy_score += 1

    elif 30 < rsi < 50:

        sell_score += 1

    # Candle
    if last["close"] > last["open"]:

        buy_score += 1

    elif last["close"] < last["open"]:

        sell_score += 1

    # Breakout
    if last["close"] > previous["high"]:

        buy_score += 2

    elif last["close"] < previous["low"]:

        sell_score += 2

    if buy_score > sell_score:

        trend = "BULLISH"

    elif sell_score > buy_score:

        trend = "BEARISH"

    else:

        trend = "NEUTRAL"

    return {
        "price": closes[-1],
        "ema20": ema20,
        "ema50": ema50,
        "rsi": rsi,
        "trend": trend,
        "buy_score": buy_score,
        "sell_score": sell_score,
        "candles": candles
    }


# ============================================================
# SIGNAL
# ============================================================

def generate_signal():

    tf15 = analyze_timeframe(
        "15min"
    )

    tf5 = analyze_timeframe(
        "5min"
    )

    tf1 = analyze_timeframe(
        "1min"
    )

    if not tf15 or not tf5 or not tf1:

        return {
            "signal": "WAIT",
            "error": True
        }

    buy_score = 0

    sell_score = 0

    # 15M
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

    price = tf1["price"]

    atr = calculate_atr(
        tf1["candles"],
        14
    )

    # BUY
    if (
        buy_score >= 7 and
        buy_score > sell_score
    ):

        entry = price

        sl = (
            entry -
            atr * 1.2
        )

        risk = (
            entry -
            sl
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

        entry = price

        sl = (
            entry +
            atr * 1.2
        )

        risk = (
            sl -
            entry
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
        "price": price,
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

    if result.get("error"):

        return (
            "❌ <b>XAU/USD</b>\n\n"
            "Market data yetarli emas."
        )

    if result["signal"] == "WAIT":

        return (
            "🟡 <b>XAU/USD</b>\n\n"
            "⏳ <b>WAIT</b>\n\n"
            f"💰 Price: "
            f"<b>{result['price']:.2f}</b>\n\n"
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
# ALPHA VANTAGE NEWS
# ============================================================

def get_news():

    if not ALPHA_VANTAGE_API_KEY:

        print(
            "ALPHA_VANTAGE_API_KEY missing"
        )

        return []

    try:

        response = requests.get(
            "https://www.alphavantage.co/query",
            params={
                "function": "NEWS_SENTIMENT",
                "tickers": "FOREX:USD",
                "limit": 10,
                "apikey": ALPHA_VANTAGE_API_KEY
            },
            timeout=TIMEOUT
        )

        if not response.ok:

            print(
                "Alpha HTTP:",
                response.status_code
            )

            return []

        data = response.json()

        if "Information" in data:

            print(
                "Alpha information:",
                data["Information"]
            )

            return []

        if "Note" in data:

            print(
                "Alpha note:",
                data["Note"]
            )

            return []

        return data.get(
            "feed",
            []
        )

    except Exception as e:

        print(
            "News error:",
            repr(e)
        )

        return []


# ============================================================
# FUNDAMENTAL
# ============================================================

def fundamental_message():

    news = get_news()

    if not news:

        return (
            "📰 <b>FUNDAMENTAL</b>\n\n"
            "Hozircha fundamental news "
            "ma'lumoti mavjud emas.\n\n"
            "API limit yoki news source "
            "vaqtincha unavailable bo‘lishi mumkin."
        )

    bullish = 0

    bearish = 0

    neutral = 0

    lines = []

    for item in news[:5]:

        title = item.get(
            "title",
            "Unknown news"
        )

        sentiment = item.get(
            "overall_sentiment_label",
            "Neutral"
        )

        if "Bullish" in sentiment:

            bullish += 1

        elif "Bearish" in sentiment:

            bearish += 1

        else:

            neutral += 1

        lines.append(
            f"📰 {title[:100]}\n"
            f"Sentiment: <b>{sentiment}</b>"
        )

    if bullish > bearish:

        bias = "🟢 BULLISH"

    elif bearish > bullish:

        bias = "🔴 BEARISH"

    else:

        bias = "🟡 NEUTRAL"

    return (
        "📰 <b>FUNDAMENTAL ANALYSIS</b>\n\n"
        f"USD/Gold news bias: "
        f"<b>{bias}</b>\n\n"
        f"🟢 Bullish: {bullish}\n"
        f"🔴 Bearish: {bearish}\n"
        f"🟡 Neutral: {neutral}\n\n"
        +
        "\n\n".join(lines)
        +
        "\n\n"
        "⚠️ News sentiment — "
        "signalni tasdiqlovchi qo‘shimcha "
        "ma'lumot sifatida ishlatiladi."
    )


# ============================================================
# NEWS
# ============================================================

def news_message():

    news = get_news()

    if not news:

        return (
            "📅 <b>MARKET NEWS</b>\n\n"
            "Hozircha news mavjud emas."
        )

    lines = []

    for item in news[:8]:

        title = item.get(
            "title",
            "Unknown"
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
# MARKET ANALYSIS
# ============================================================

def market_analysis_message():

    tf15 = analyze_timeframe(
        "15min"
    )

    tf5 = analyze_timeframe(
        "5min"
    )

    tf1 = analyze_timeframe(
        "1min"
    )

    if not tf15 or not tf5 or not tf1:

        return (
            "📈 <b>MARKET ANALYSIS</b>\n\n"
            "Market data yetarli emas."
        )

    total_buy = (
        tf15["buy_score"] +
        tf5["buy_score"] +
        tf1["buy_score"]
    )

    total_sell = (
        tf15["sell_score"] +
        tf5["sell_score"] +
        tf1["sell_score"]
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
        f"🟢 Buy score: "
        f"<b>{total_buy}</b>\n"
        f"🔴 Sell score: "
        f"<b>{total_sell}</b>"
    )


# ============================================================
# AI ADVISOR
# ============================================================

def advisor_message():

    signal = generate_signal()

    price = get_gold_price()

    if price is None:

        price = signal.get(
            "price",
            0
        )

    if signal.get("error"):

        return (
            "🤖 <b>AI ADVISOR</b>\n\n"
            "Market data yetarli emas."
        )

    if signal["signal"] == "BUY":

        verdict = (
            "🟢 <b>BUY SETUP</b>\n\n"
            "Technical sharoit BUY tomonida."
        )

    elif signal["signal"] == "SELL":

        verdict = (
            "🔴 <b>SELL SETUP</b>\n\n"
            "Technical sharoit SELL tomonida."
        )

    else:

        verdict = (
            "🟡 <b>WAIT</b>\n\n"
            "Kuchli confirmation hozircha yo‘q."
        )

    return (
        "🤖 <b>BEGZOD AI ADVISOR</b>\n\n"
        f"🥇 Price: "
        f"<b>{price:.2f}</b>\n\n"
        f"📊 Technical: "
        f"<b>{signal['signal']}</b>\n\n"
        f"{verdict}\n\n"
        "🧠 Advisor hozircha technical "
        "signalga asoslanadi.\n\n"
        "Keyingi versiyada fundamental + "
        "economic calendar + news risk "
        "birlashtiriladi.\n\n"
        "⚠️ Avtomatik tahlil. "
        "Moliyaviy maslahat emas."
    )


# ============================================================
# SETTINGS
# ============================================================

def settings_message():

    return (
        "⚙️ <b>SETTINGS</b>\n\n"
        "🥇 Symbol: XAU/USD\n"
        "📊 Timeframes: 15M / 5M / 1M\n"
        "📐 SL: ATR based\n"
        "💰 TP: 1R / 2R / 3R\n\n"
        "Keyingi versiyalar:\n"
        "• Risk %\n"
        "• News filter\n"
        "• Trading sessions\n"
        "• Alerts"
    )


# ============================================================
# UPDATE PROCESSOR
# ============================================================

def process_update(
    update
):

    try:

        if "message" not in update:

            return

        message = update[
            "message"
        ]

        chat_id = message[
            "chat"
        ]["id"]

        text = message.get(
            "text",
            ""
        ).strip()

        print(
            "MESSAGE:",
            text
        )

        # ----------------------------------------------------
        # START
        # ----------------------------------------------------

        if text == "/start":

            send_main_menu(
                chat_id
            )

            return

        # ----------------------------------------------------
        # HELP
        # ----------------------------------------------------

        if text == "/help":

            send_message(
                chat_id,
                (
                    "📚 <b>HELP</b>\n\n"
                    "/start — Asosiy menyu\n"
                    "/price — Live price\n"
                    "/signal — Signal\n"
                    "/fundamental — Fundamental\n"
                    "/news — News\n"
                    "/advisor — AI Advisor\n"
                    "/market — Market analysis"
                ),
                main_keyboard()
            )

            return

        # ----------------------------------------------------
        # PRICE
        # ----------------------------------------------------

        if text in (
            "/price",
            "🥇 Live Price"
        ):

            send_message(
                chat_id,
                "🔎 XAU/USD narxi olinmoqda..."
            )

            price = get_gold_price()

            if price is None:

                send_message(
                    chat_id,
                    (
                        "❌ XAU/USD narxini "
                        "olib bo‘lmadi.\n\n"
                        "Twelve Data API "
                        "tekshirilishi kerak."
                    ),
                    main_keyboard()
                )

            else:

                send_message(
                    chat_id,
                    (
                        "🥇 <b>XAU/USD</b>\n\n"
                        f"💰 Live Price: "
                        f"<b>{price:.2f}</b>"
                    ),
                    main_keyboard()
                )

            return

        # ----------------------------------------------------
        # SIGNAL
        # ----------------------------------------------------

        if text in (
            "/signal",
            "📊 Signal"
        ):

            send_message(
                chat_id,
                "🔎 XAU/USD analiz qilinmoqda..."
            )

            try:

                result = signal_message()

                send_message(
                    chat_id,
                    result,
                    main_keyboard()
                )

            except Exception as e:

                print(
                    "SIGNAL ERROR:",
                    repr(e)
                )

                send_message(
                    chat_id,
                    (
                        "❌ Signal xatosi.\n\n"
                        "Logni tekshiring."
                    ),
                    main_keyboard()
                )

            return

        # ----------------------------------------------------
        # FUNDAMENTAL
        # ----------------------------------------------------

        if text in (
            "/fundamental",
            "📰 Fundamental"
        ):

            send_message(
                chat_id,
                "📰 Fundamental ma'lumotlar olinmoqda..."
            )

            try:

                send_message(
                    chat_id,
                    fundamental_message(),
                    main_keyboard()
                )

            except Exception as e:

                print(
                    "FUNDAMENTAL ERROR:",
                    repr(e)
                )

                send_message(
                    chat_id,
                    "❌ Fundamental analiz xatosi.",
                    main_keyboard()
                )

            return

        # ----------------------------------------------------
        # NEWS
        # ----------------------------------------------------

        if text in (
            "/news",
            "📅 News"
        ):

            send_message(
                chat_id,
                "📅 News olinmoqda..."
            )

            try:

                send_message(
                    chat_id,
                    news_message(),
                    main_keyboard()
                )

            except Exception as e:

                print(
                    "NEWS ERROR:",
                    repr(e)
                )

                send_message(
                    chat_id,
                    "❌ News xatosi.",
                    main_keyboard()
                )

            return

        # ----------------------------------------------------
        # AI ADVISOR
        # ----------------------------------------------------

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
                    advisor_message(),
                    main_keyboard()
                )

            except Exception as e:

                print(
                    "ADVISOR ERROR:",
                    repr(e)
                )

                send_message(
                    chat_id,
                    "❌ Advisor xatosi.",
                    main_keyboard()
                )

            return

        # ----------------------------------------------------
        # MARKET
        # ----------------------------------------------------

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
                    market_analysis_message(),
                    main_keyboard()
                )

            except Exception as e:

                print(
                    "MARKET ERROR:",
                    repr(e)
                )

                send_message(
                    chat_id,
                    "❌ Market analysis xatosi.",
                    main_keyboard()
                )

            return

        # ----------------------------------------------------
        # SETTINGS
        # ----------------------------------------------------

        if text == "⚙️ Settings":

            send_message(
                chat_id,
                settings_message(),
                main_keyboard()
            )

            return

        # ----------------------------------------------------
        # UNKNOWN
        # ----------------------------------------------------

        send_message(
            chat_id,
            (
                "❓ Buyruq topilmadi.\n\n"
                "👇 Menyudan foydalaning."
            ),
            main_keyboard()
        )

    except Exception as e:

        print(
            "PROCESS UPDATE ERROR:",
            repr(e)
        )


# ============================================================
# DELETE WEBHOOK
# ============================================================

def delete_webhook():

    try:

        result = telegram_request(
            "deleteWebhook",
            {
                "drop_pending_updates": "true"
            }
        )

        print(
            "Webhook deleted:",
            result
        )

    except Exception as e:

        print(
            "Webhook delete error:",
            repr(e)
        )


# ============================================================
# TELEGRAM POLLING
# ============================================================

def telegram_loop():

    print(
        "======================================"
    )

    print(
        "TELEGRAM POLLING STARTED"
    )

    print(
        "======================================"
    )

    offset = None

    while True:

        try:

            params = {
                "timeout": 30
            }

            if offset is not None:

                params[
                    "offset"
                ] = offset

            response = requests.get(
                f"{TELEGRAM_API}/getUpdates",
                params=params,
                timeout=40
            )

            if not response.ok:

                print(
                    "Polling HTTP ERROR:",
                    response.status_code
                )

                time.sleep(5)

                continue

            data = response.json()

            if not data.get("ok"):

                print(
                    "Polling API ERROR:",
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
                    update[
                        "update_id"
                    ] + 1
                )

                process_update(
                    update
                )

        except Exception as e:

            print(
                "POLLING ERROR:",
                repr(e)
            )

            time.sleep(5)


# ============================================================
# RENDER HEALTH SERVER
# ============================================================

class HealthHandler(
    BaseHTTPRequestHandler
):

    def do_GET(
        self
    ):

        self.send_response(
            200
        )

        self.send_header(
            "Content-Type",
            "text/plain"
        )

        self.end_headers()

        self.wfile.write(
            b"BEGZOD AI XAUUSD BOT IS RUNNING"
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
# MAIN
# ============================================================

if __name__ == "__main__":

    print(
        "======================================"
    )

    print(
        "STARTING BEGZOD AI XAUUSD BOT"
    )

    print(
        "======================================"
    )

    delete_webhook()

    threading.Thread(
        target=start_server,
        daemon=True
    ).start()

    telegram_loop()
  
