import os
import time
import json
import threading
import requests

from http.server import BaseHTTPRequestHandler, HTTPServer


# ============================================================
# BEGZOD AI XAUUSD V3
# ============================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
TWELVE_API_KEY = os.getenv("TWELVE_API_KEY")

SYMBOL = "XAU/USD"

TELEGRAM_API = ""

if BOT_TOKEN:
    TELEGRAM_API = "https://api.telegram.org/bot" + BOT_TOKEN

REQUEST_TIMEOUT = 25

MIN_SCORE = 8
SL_ATR_MULTIPLIER = 1.20


# ============================================================
# STARTUP
# ============================================================

print("========================================")
print("BEGZOD AI XAUUSD V3")
print("========================================")

print("BOT_TOKEN:", "OK" if BOT_TOKEN else "MISSING")
print(
    "TWELVE_API_KEY:",
    "OK" if TWELVE_API_KEY else "MISSING"
)


# ============================================================
# TELEGRAM API
# ============================================================

def telegram_request(method, data=None):

    if not BOT_TOKEN:
        print("ERROR: BOT_TOKEN missing")
        return None

    try:

        response = requests.post(
            TELEGRAM_API + "/" + method,
            data=data or {},
            timeout=REQUEST_TIMEOUT
        )

        print(
            "Telegram:",
            method,
            response.status_code
        )

        if not response.ok:
            print(response.text[:500])
            return None

        result = response.json()

        if not result.get("ok"):
            print("Telegram API error:", result)
            return None

        return result

    except Exception as e:

        print("Telegram request error:", repr(e))
        return None


def send_message(chat_id, text, use_keyboard=True):

    data = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }

    if use_keyboard:

        data["reply_markup"] = json.dumps(
            main_keyboard(),
            ensure_ascii=False
        )

    telegram_request(
        "sendMessage",
        data
    )


# ============================================================
# KEYBOARD
# ============================================================

def main_keyboard():

    return {
        "keyboard": [
            [
                {"text": "🥇 Live Price"},
                {"text": "📊 Signal"}
            ],
            [
                {"text": "📈 Market Analysis"},
                {"text": "🤖 AI Advisor"}
            ],
            [
                {"text": "📰 Fundamental"},
                {"text": "📅 News"}
            ],
            [
                {"text": "⚙️ Settings"}
            ]
        ],
        "resize_keyboard": True,
        "one_time_keyboard": False
    }


# ============================================================
# TWELVE DATA
# ============================================================

def twelve_request(endpoint, params=None):

    if not TWELVE_API_KEY:

        print("ERROR: TWELVE_API_KEY missing")

        return None

    try:

        request_params = {}

        if params:
            request_params.update(params)

        request_params["apikey"] = TWELVE_API_KEY

        url = (
            "https://api.twelvedata.com/"
            + endpoint
        )

        response = requests.get(
            url,
            params=request_params,
            timeout=REQUEST_TIMEOUT
        )

        print(
            "Twelve Data:",
            endpoint,
            response.status_code
        )

        if not response.ok:

            print(response.text[:500])

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
            "Twelve Data request error:",
            repr(e)
        )

        return None


# ============================================================
# LIVE PRICE
# ============================================================

def get_live_price():

    data = twelve_request(
        "price",
        {
            "symbol": SYMBOL
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
    outputsize=120
):

    data = twelve_request(
        "time_series",
        {
            "symbol": SYMBOL,
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

            candle = {
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

            candles.append(candle)

        except Exception:

            continue

    return candles


# ============================================================
# EMA
# ============================================================

def calculate_ema(values, period):

    if len(values) < period:
        return None

    multiplier = 2.0 / (period + 1.0)

    result = sum(
        values[:period]
    ) / period

    for value in values[period:]:

        result = (
            (value - result) * multiplier
        ) + result

    return result


# ============================================================
# RSI
# ============================================================

def calculate_rsi(values, period=14):

    if len(values) < period + 1:
        return 50.0

    gains = []
    losses = []

    for i in range(1, len(values)):

        change = (
            values[i] -
            values[i - 1]
        )

        if change > 0:

            gains.append(change)
            losses.append(0.0)

        else:

            gains.append(0.0)
            losses.append(abs(change))

    avg_gain = (
        sum(gains[:period]) /
        period
    )

    avg_loss = (
        sum(losses[:period]) /
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

    rs = avg_gain / avg_loss

    return (
        100.0 -
        (
            100.0 /
            (1.0 + rs)
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

    true_ranges = []

    for i in range(
        1,
        len(candles)
    ):

        current = candles[i]
        previous = candles[i - 1]

        high = current["high"]
        low = current["low"]
        previous_close = previous["close"]

        tr1 = high - low

        tr2 = abs(
            high -
            previous_close
        )

        tr3 = abs(
            low -
            previous_close
        )

        true_range = max(
            tr1,
            tr2,
            tr3
        )

        true_ranges.append(
            true_range
        )

    return (
        sum(
            true_ranges[-period:]
        ) / period
    )


# ============================================================
# MARKET STRUCTURE
# ============================================================

def detect_structure(candles):

    result = {
        "bos": "NONE",
        "choch": "NONE",
        "sweep": "NONE"
    }

    if len(candles) < 15:
        return result

    last = candles[-1]
    previous = candles[-2]

    lookback = candles[-12:-2]

    highest = max(
        candle["high"]
        for candle in lookback
    )

    lowest = min(
        candle["low"]
        for candle in lookback
    )

    # --------------------------------------------------------
    # BOS
    # --------------------------------------------------------

    if last["close"] > highest:

        result["bos"] = "BULLISH"

    elif last["close"] < lowest:

        result["bos"] = "BEARISH"

    # --------------------------------------------------------
    # Liquidity sweep
    # --------------------------------------------------------

    if (
        last["low"] < lowest
        and
        last["close"] > lowest
    ):

        result["sweep"] = "BULLISH"

    elif (
        last["high"] > highest
        and
        last["close"] < highest
    ):

        result["sweep"] = "BEARISH"

    # --------------------------------------------------------
    # CHoCH
    # --------------------------------------------------------

    if (
        previous["close"] <
        previous["open"]
        and
        last["close"] >
        previous["high"]
    ):

        result["choch"] = "BULLISH"

    elif (
        previous["close"] >
        previous["open"]
        and
        last["close"] <
        previous["low"]
    ):

        result["choch"] = "BEARISH"

    return result


# ============================================================
# TIMEFRAME ANALYSIS
# ============================================================

def analyze_timeframe(interval):

    candles = get_candles(
        interval,
        120
    )

    if len(candles) < 60:

        print(
            "Not enough candles:",
            interval,
            len(candles)
        )

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

    atr = calculate_atr(
        candles,
        14
    )

    last = candles[-1]

    bullish_candle = (
        last["close"] >
        last["open"]
    )

    bearish_candle = (
        last["close"] <
        last["open"]
    )

    trend = "NEUTRAL"

    if (
        ema20 is not None
        and
        ema50 is not None
    ):

        if ema20 > ema50:

            trend = "BULLISH"

        elif ema20 < ema50:

            trend = "BEARISH"

    structure = detect_structure(
        candles
    )

    return {
        "candles": candles,
        "price": last["close"],
        "ema20": ema20,
        "ema50": ema50,
        "rsi": rsi,
        "atr": atr,
        "trend": trend,
        "bullish_candle": bullish_candle,
        "bearish_candle": bearish_candle,
        "bos": structure["bos"],
        "choch": structure["choch"],
        "sweep": structure["sweep"]
    }


# ============================================================
# SIGNAL ENGINE
# ============================================================

def generate_signal():

    print("Starting signal analysis...")

    tf15 = analyze_timeframe(
        "15min"
    )

    tf5 = analyze_timeframe(
        "5min"
    )

    tf1 = analyze_timeframe(
        "1min"
    )

    if (
        tf15 is None
        or
        tf5 is None
        or
        tf1 is None
    ):

        return {
            "signal": "WAIT",
            "error": (
                "Twelve Data'dan "
                "yetarli candle olinmadi."
            )
        }

    buy_score = 0
    sell_score = 0

    buy_reasons = []
    sell_reasons = []

    # ========================================================
    # 15M TREND
    # ========================================================

    if tf15["trend"] == "BULLISH":

        buy_score += 3

        buy_reasons.append(
            "15M bullish trend"
        )

    elif tf15["trend"] == "BEARISH":

        sell_score += 3

        sell_reasons.append(
            "15M bearish trend"
        )

    # ========================================================
    # 5M TREND
    # ========================================================

    if tf5["trend"] == "BULLISH":

        buy_score += 2

        buy_reasons.append(
            "5M bullish trend"
        )

    elif tf5["trend"] == "BEARISH":

        sell_score += 2

        sell_reasons.append(
            "5M bearish trend"
        )

    # ========================================================
    # 1M TREND
    # ========================================================

    if tf1["trend"] == "BULLISH":

        buy_score += 1

        buy_reasons.append(
            "1M bullish trend"
        )

    elif tf1["trend"] == "BEARISH":

        sell_score += 1

        sell_reasons.append(
            "1M bearish trend"
        )

    # ========================================================
    # 5M RSI
    # ========================================================

    if (
        tf5["rsi"] > 50
        and
        tf5["rsi"] < 70
    ):

        buy_score += 1

        buy_reasons.append(
            "5M RSI bullish"
        )

    elif (
        tf5["rsi"] > 30
        and
        tf5["rsi"] < 50
    ):

        sell_score += 1

        sell_reasons.append(
            "5M RSI bearish"
        )

    # ========================================================
    # 1M RSI
    # ========================================================

    if (
        tf1["rsi"] > 50
        and
        tf1["rsi"] < 70
    ):

        buy_score += 1

        buy_reasons.append(
            "1M RSI bullish"
        )

    elif (
        tf1["rsi"] > 30
        and
        tf1["rsi"] < 50
    ):

        sell_score += 1

        sell_reasons.append(
            "1M RSI bearish"
        )

    # ========================================================
    # 5M BOS
    # ========================================================

    if tf5["bos"] == "BULLISH":

        buy_score += 2

        buy_reasons.append(
            "5M bullish BOS"
        )

    elif tf5["bos"] == "BEARISH":

        sell_score += 2

        sell_reasons.append(
            "5M bearish BOS"
        )

    # ========================================================
    # 1M BOS
    # ========================================================

    if tf1["bos"] == "BULLISH":

        buy_score += 2

        buy_reasons.append(
            "1M bullish BOS"
        )

    elif tf1["bos"] == "BEARISH":

        sell_score += 2

        sell_reasons.append(
            "1M bearish BOS"
        )

    # ========================================================
    # CHOCH
    # ========================================================

    if tf1["choch"] == "BULLISH":

        buy_score += 2

        buy_reasons.append(
            "1M bullish CHoCH"
        )

    elif tf1["choch"] == "BEARISH":

        sell_score += 2

        sell_reasons.append(
            "1M bearish CHoCH"
        )

    # ========================================================
    # LIQUIDITY SWEEP
    # ========================================================

    if tf1["sweep"] == "BULLISH":

        buy_score += 2

        buy_reasons.append(
            "1M bullish liquidity sweep"
        )

    elif tf1["sweep"] == "BEARISH":

        sell_score += 2

        sell_reasons.append(
            "1M bearish liquidity sweep"
        )

    # ========================================================
    # CANDLE
    # ========================================================

    if tf1["bullish_candle"]:

        buy_score += 1

        buy_reasons.append(
            "1M bullish candle"
        )

    elif tf1["bearish_candle"]:

        sell_score += 1

        sell_reasons.append(
            "1M bearish candle"
        )

    # ========================================================
    # CONFIDENCE SCORE
    # ========================================================

    best_score = max(
        buy_score,
        sell_score
    )

    confidence = min(
        99,
        int(
            best_score *
            100 /
            18
        )
    )

    # ========================================================
    # BUY
    # ========================================================

    if (
        buy_score >= MIN_SCORE
        and
        buy_score > sell_score
    ):

        entry = tf1["price"]

        risk = (
            tf1["atr"] *
            SL_ATR_MULTIPLIER
        )

        if risk <= 0:
            risk = 2.0

        stop_loss = (
            entry -
            risk
        )

        tp1 = entry + risk
        tp2 = entry + risk * 2.0
        tp3 = entry + risk * 3.0

        return {
            "signal": "BUY",
            "entry": entry,
            "sl": stop_loss,
            "tp1": tp1,
            "tp2": tp2,
            "tp3": tp3,
            "confidence": confidence,
            "buy_score": buy_score,
            "sell_score": sell_score,
            "tf15": tf15,
            "tf5": tf5,
            "tf1": tf1,
            "reasons": buy_reasons
        }

    # ========================================================
    # SELL
    # ========================================================

    if (
        sell_score >= MIN_SCORE
        and
        sell_score > buy_score
    ):

        entry = tf1["price"]

        risk = (
            tf1["atr"] *
            SL_ATR_MULTIPLIER
        )

        if risk <= 0:
            risk = 2.0

        stop_loss = (
            entry +
            risk
        )

        tp1 = entry - risk
        tp2 = entry - risk * 2.0
        tp3 = entry - risk * 3.0

        return {
            "signal": "SELL",
            "entry": entry,
            "sl": stop_loss,
            "tp1": tp1,
            "tp2": tp2,
            "tp3": tp3,
            "confidence": confidence,
            "buy_score": buy_score,
            "sell_score": sell_score,
            "tf15": tf15,
            "tf5": tf5,
            "tf1": tf1,
            "reasons": sell_reasons
        }

    # ========================================================
    # WAIT
    # ========================================================

    return {
        "signal": "WAIT",
        "price": tf1["price"],
        "confidence": confidence,
        "buy_score": buy_score,
        "sell_score": sell_score,
        "tf15": tf15,
        "tf5": tf5,
        "tf1": tf1
    }


# ============================================================
# SIGNAL MESSAGE
# ============================================================

def format_signal():

    result = generate_signal()

    if result.get("error"):

        return (
            "❌ <b>DATA ERROR</b>\n\n"
            + result["error"]
        )

    tf15 = result["tf15"]
    tf5 = result["tf5"]
    tf1 = result["tf1"]

    # --------------------------------------------------------
    # WAIT
    # --------------------------------------------------------

    if result["signal"] == "WAIT":

        return (
            "🟡 <b>XAU/USD</b>\n\n"
            "⏳ <b>WAIT</b>\n\n"

            "💰 Price: "
            f"<b>{result['price']:.2f}</b>\n\n"

            "📊 15M Trend: "
            f"<b>{tf15['trend']}</b>\n"

            "📊 5M Trend: "
            f"<b>{tf5['trend']}</b>\n"

            "📊 1M Trend: "
            f"<b>{tf1['trend']}</b>\n\n"

            "📈 5M RSI: "
            f"<b>{tf5['rsi']:.1f}</b>\n"

            "📉 1M RSI: "
            f"<b>{tf1['rsi']:.1f}</b>\n\n"

            "🟢 Buy score: "
            f"<b>{result['buy_score']}</b>\n"

            "🔴 Sell score: "
            f"<b>{result['sell_score']}</b>\n\n"

            "🧠 Score confidence: "
            f"<b>{result['confidence']}%</b>\n\n"

            "❌ Kuchli entry tasdig‘i yo‘q."
        )

    # --------------------------------------------------------
    # BUY / SELL
    # --------------------------------------------------------

    emoji = (
        "🟢"
        if result["signal"] == "BUY"
        else "🔴"
    )

    reasons = result.get(
        "reasons",
        []
    )

    reason_text = ""

    for reason in reasons[:8]:

        reason_text += (
            "• " +
            reason +
            "\n"
        )

    return (
        f"{emoji} <b>XAU/USD "
        f"{result['signal']}</b>\n\n"

        "🎯 Entry: "
        f"<b>{result['entry']:.2f}</b>\n"

        "🛑 Stop Loss: "
        f"<b>{result['sl']:.2f}</b>\n\n"

        "💰 TP1: "
        f"<b>{result['tp1']:.2f}</b>\n"

        "💰 TP2: "
        f"<b>{result['tp2']:.2f}</b>\n"

        "💰 TP3: "
        f"<b>{result['tp3']:.2f}</b>\n\n"

        "📊 15M: "
        f"<b>{tf15['trend']}</b>\n"

        "📊 5M: "
        f"<b>{tf5['trend']}</b>\n"

        "📊 1M: "
        f"<b>{tf1['trend']}</b>\n\n"

        "📈 5M RSI: "
        f"<b>{tf5['rsi']:.1f}</b>\n"

        "📉 1M RSI: "
        f"<b>{tf1['rsi']:.1f}</b>\n\n"

        "🔎 <b>STRUCTURE</b>\n"

        "5M BOS: "
        f"<b>{tf5['bos']}</b>\n"

        "1M BOS: "
        f"<b>{tf1['bos']}</b>\n"

        "1M CHoCH: "
        f"<b>{tf1['choch']}</b>\n"

        "1M Liquidity: "
        f"<b>{tf1['sweep']}</b>\n\n"

        "🧠 Score confidence: "
        f"<b>{result['confidence']}%</b>\n\n"

        "✅ <b>CONFIRMATIONS</b>\n"
        + reason_text +

        "\n⚠️ Confidence texnik "
        "score hisobidir, kafolatlangan "
        "win-rate emas."
    )


# ============================================================
# MARKET ANALYSIS
# ============================================================

def format_market():

    tf15 = analyze_timeframe(
        "15min"
    )

    tf5 = analyze_timeframe(
        "5min"
    )

    tf1 = analyze_timeframe(
        "1min"
    )

    if (
        tf15 is None
        or
        tf5 is None
        or
        tf1 is None
    ):

        return (
            "❌ Market data yetarli emas."
        )

    return (
        "📈 <b>MARKET ANALYSIS</b>\n\n"

        "🥇 Price: "
        f"<b>{tf1['price']:.2f}</b>\n\n"

        "15M: "
        f"<b>{tf15['trend']}</b>\n"

        "5M: "
        f"<b>{tf5['trend']}</b>\n"

        "1M: "
        f"<b>{tf1['trend']}</b>\n\n"

        "📊 5M RSI: "
        f"<b>{tf5['rsi']:.1f}</b>\n"

        "📊 1M RSI: "
        f"<b>{tf1['rsi']:.1f}</b>\n\n"

        "🔎 <b>STRUCTURE</b>\n"

        "5M BOS: "
        f"<b>{tf5['bos']}</b>\n"

        "1M BOS: "
        f"<b>{tf1['bos']}</b>\n"

        "1M CHoCH: "
        f"<b>{tf1['choch']}</b>\n"

        "1M Liquidity: "
        f"<b>{tf1['sweep']}</b>"
    )


# ============================================================
# AI ADVISOR
# ============================================================

def format_advisor():

    result = generate_signal()

    if result.get("error"):

        return (
            "🤖 <b>AI ADVISOR</b>\n\n"
            "❌ Market data yetarli emas."
        )

    tf15 = result["tf15"]
    tf5 = result["tf5"]
    tf1 = result["tf1"]

    if result["signal"] == "BUY":

        advice = (
            "🟢 Texnik bias BUY.\n"
            "Entry faqat SL bilan ishlatilishi kerak."
        )

    elif result["signal"] == "SELL":

        advice = (
            "🔴 Texnik bias SELL.\n"
            "Entry faqat SL bilan ishlatilishi kerak."
        )

    else:

        advice = (
            "🟡 Hozircha WAIT.\n"
            "Bozor yetarli confirmation bermadi."
        )

    return (
        "🤖 <b>BEGZOD AI ADVISOR</b>\n\n"

        "🥇 Price: "
        f"<b>{tf1['price']:.2f}</b>\n\n"

        "📊 15M: "
        f"<b>{tf15['trend']}</b>\n"

        "📊 5M: "
        f"<b>{tf5['trend']}</b>\n"

        "📊 1M: "
        f"<b>{tf1['trend']}</b>\n\n"

        "🧠 Buy score: "
        f"<b>{result['buy_score']}</b>\n"

        "🧠 Sell score: "
        f"<b>{result['sell_score']}</b>\n\n"

        "📌 Advice:\n"
        f"{advice}\n\n"

        "⚠️ Bu avtomatik texnik maslahat."
    )


# ============================================================
# START
# ============================================================

def handle_start(chat_id):

    send_message(
        chat_id,
        (
            "🤖 <b>BEGZOD AI XAU/USD V3</b>\n\n"

            "🥇 Real-time XAU/USD\n"
            "📊 15M + 5M + 1M\n"
            "🧠 Market Structure\n"
            "💧 Liquidity\n"
            "📐 BOS / CHoCH\n"
            "🎯 Entry / SL / TP\n\n"

            "👇 Kerakli bo‘limni tanlang."
        )
    )


# ============================================================
# UPDATE PROCESSOR
# ============================================================

def process_update(update):

    try:

        if "message" not in update:
            return

        message = update["message"]

        chat_id = message["chat"]["id"]

        text = message.get(
            "text",
            ""
        ).strip()

        print(
            "Incoming:",
            text
        )

        # ----------------------------------------------------
        # START
        # ----------------------------------------------------

        if text == "/start":

            handle_start(
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
                    "📚 <b>YORDAM</b>\n\n"

                    "/start — Botni boshlash\n"
                    "/price — Live narx\n"
                    "/signal — Signal\n"
                    "/market — Market analysis\n"
                    "/advisor — AI maslahat\n"
                    "/help — Yordam"
                )
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
                "🔎 Live XAU/USD narxi olinmoqda...",
                False
            )

            price = get_live_price()

            if price is None:

                send_message(
                    chat_id,
                    (
                        "❌ Narx olinmadi.\n\n"
                        "Twelve Data API "
                        "tekshiring."
                    )
                )

            else:

                send_message(
                    chat_id,
                    (
                        "🥇 <b>XAU/USD</b>\n\n"
                        "💰 Live Price: "
                        f"<b>{price:.2f}</b>"
                    )
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
                "🔎 XAU/USD V3 analiz qilinmoqda...",
                False
            )

            try:

                result = format_signal()

                send_message(
                    chat_id,
                    result
                )

            except Exception as e:

                print(
                    "SIGNAL ERROR:",
                    repr(e)
                )

                send_message(
                    chat_id,
                    (
                        "❌ Analiz xatosi.\n\n"
                        "Render Logsni tekshiring."
                    )
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
                "📈 Market analiz qilinmoqda...",
                False
            )

            try:

                result = format_market()

                send_message(
                    chat_id,
                    result
                )

            except Exception as e:

                print(
                    "MARKET ERROR:",
                    repr(e)
                )

                send_message(
                    chat_id,
                    "❌ Market analysis xatosi."
                )

            return

        # ----------------------------------------------------
        # ADVISOR
        # ----------------------------------------------------

        if text in (
            "/advisor",
            "🤖 AI Advisor"
        ):

            send_message(
                chat_id,
                "🤖 AI Advisor ishlamoqda...",
                False
            )

            try:

                result = format_advisor()

                send_message(
                    chat_id,
                    result
                )

            except Exception as e:

                print(
                    "ADVISOR ERROR:",
                    repr(e)
                )

                send_message(
                    chat_id,
                    "❌ Advisor xatosi."
                )

            return

        # ----------------------------------------------------
        # FUNDAMENTAL
        # ----------------------------------------------------

        if text in (
            "📰 Fundamental",
            "/fundamental"
        ):

            send_message(
                chat_id,
                (
                    "📰 <b>FUNDAMENTAL</b>\n\n"
                    "Fundamental/news modulini "
                    "keyingi bosqichda kuchaytiramiz.\n\n"
                    "Hozirgi V3 signal engine "
                    "texnik analizdan foydalanadi."
                )
            )

            return

        # ----------------------------------------------------
        # NEWS
        # ----------------------------------------------------

        if text in (
            "📅 News",
            "/news"
        ):

            send_message(
                chat_id,
                (
                    "📅 <b>MARKET NEWS</b>\n\n"
                    "News moduli hozircha "
                    "alohida ishlaydi.\n\n"
                    "Agar news API ma'lumot "
                    "bermasa, bot WAIT rejimida "
                    "qoladi."
                )
            )

            return

        # ----------------------------------------------------
        # SETTINGS
        # ----------------------------------------------------

        if text == "⚙️ Settings":

            send_message(
                chat_id,
                (
                    "⚙️ <b>SETTINGS</b>\n\n"
                    "Symbol: XAU/USD\n"
                    "Timeframes: 15M / 5M / 1M\n"
                    "SL: ATR × 1.20\n"
                    "TP: 1R / 2R / 3R\n"
                    "Minimum score: 8"
                )
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
            )
        )

    except Exception as e:

        print(
            "PROCESS ERROR:",
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
            "Webhook result:",
            result
        )

    except Exception as e:

        print(
            "Webhook error:",
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
                TELEGRAM_API + "/getUpdates",
                params=params,
                timeout=40
            )

            if not response.ok:

                print(
                    "Polling HTTP error:",
                    response.status_code
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
            b"BEGZOD AI XAUUSD V3 RUNNING"
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
        "Health server running on port",
        port
    )

    server.serve_forever()


# ============================================================
# MAIN
# ============================================================

def main():

    print(
        "Starting BEGZOD AI XAUUSD V3..."
    )

    if not BOT_TOKEN:

        print(
            "WARNING: BOT_TOKEN is missing."
        )

    if not TWELVE_API_KEY:

        print(
            "WARNING: TWELVE_API_KEY is missing."
        )

    if BOT_TOKEN:

        delete_webhook()

    threading.Thread(
        target=start_server,
        daemon=True
    ).start()

    if not BOT_TOKEN:

        print(
            "Bot cannot start without BOT_TOKEN."
        )

        while True:

            time.sleep(60)

    telegram_loop()


if __name__ == "__main__":

    main()
