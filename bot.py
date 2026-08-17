import os
import time
import json
import threading
import requests

from http.server import BaseHTTPRequestHandler, HTTPServer


# ============================================================
# BEGZOD AI XAUUSD — V3.1
# ============================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
TWELVE_API_KEY = os.getenv("TWELVE_API_KEY")

TELEGRAM_API = (
    f"https://api.telegram.org/bot{BOT_TOKEN}"
    if BOT_TOKEN
    else ""
)

SYMBOL = "XAU/USD"
TIMEOUT = 25

# Signal settings
MIN_SCORE = 8
RR1 = 1.0
RR2 = 2.0
RR3 = 3.0

# ATR multiplier for SL
SL_ATR_MULTIPLIER = 1.20


# ============================================================
# STARTUP
# ============================================================

print("======================================")
print("BEGZOD AI XAUUSD V3.1")
print("======================================")

print(
    "BOT_TOKEN:",
    "OK" if BOT_TOKEN else "MISSING"
)

print(
    "TWELVE_API_KEY:",
    "OK" if TWELVE_API_KEY else "MISSING"
)


# ============================================================
# TELEGRAM
# ============================================================

def telegram_request(method, data=None):

    if not BOT_TOKEN:
        print("BOT_TOKEN missing")
        return None

    try:

        response = requests.post(
            f"{TELEGRAM_API}/{method}",
            data=data or {},
            timeout=TIMEOUT
        )

        if not response.ok:

            print(
                "Telegram HTTP error:",
                response.status_code,
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
            "Telegram error:",
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

    telegram_request(
        "sendMessage",
        data
    )


# ============================================================
# MENU
# ============================================================

def keyboard():

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


def start_message(chat_id):

    send_message(
        chat_id,
        (
            "🤖 <b>BEGZOD AI XAUUSD V3.1</b>\n\n"
            "🥇 Real-time XAU/USD\n"
            "📊 15M + 5M + 1M\n"
            "🧠 Market Structure\n"
            "💧 Liquidity Sweep\n"
            "📐 BOS / CHoCH\n"
            "🎯 Entry / SL / TP\n\n"
            "👇 Bo‘limni tanlang:"
        ),
        keyboard()
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

        p = dict(
            params or {}
        )

        p["apikey"] = TWELVE_API_KEY

        response = requests.get(
            f"https://api.twelvedata.com/{endpoint}",
            params=p,
            timeout=TIMEOUT
        )

        if not response.ok:

            print(
                "Twelve HTTP error:",
                response.status_code
            )

            return None

        data = response.json()

        if data.get("status") == "error":

            print(
                "Twelve Data error:",
                data
            )

            return None

        return data

    except Exception as e:

        print(
            "Twelve Data exception:",
            repr(e)
        )

        return None


# ============================================================
# PRICE
# ============================================================

def get_price():

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

    except Exception:

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

def ema(
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

def rsi(
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
        ) /
        period

        avg_loss = (
            (
                avg_loss *
                (period - 1)
            ) +
            losses[i]
        ) /
        period

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

def atr(
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

        ranges.append(tr)

    return (
        sum(
            ranges[-period:]
        ) /
        period
    )


# ============================================================
# MARKET STRUCTURE
# ============================================================

def structure(candles):

    if len(candles) < 10:

        return {
            "bos": "NONE",
            "choch": "NONE",
            "sweep": "NONE"
        }

    last = candles[-1]

    previous = candles[-2]

    lookback = candles[-7:-2]

    highest = max(
        c["high"]
        for c in lookback
    )

    lowest = min(
        c["low"]
        for c in lookback
    )

    bos = "NONE"
    sweep = "NONE"
    choch = "NONE"

    # --------------------------------------------------------
    # Bullish BOS
    # --------------------------------------------------------

    if last["close"] > highest:

        bos = "BULLISH"

    # --------------------------------------------------------
    # Bearish BOS
    # --------------------------------------------------------

    elif last["close"] < lowest:

        bos = "BEARISH"

    # --------------------------------------------------------
    # Liquidity sweep
    # --------------------------------------------------------

    if (
        last["low"] < lowest
        and
        last["close"] > lowest
    ):

        sweep = "BULLISH"

    elif (
        last["high"] > highest
        and
        last["close"] < highest
    ):

        sweep = "BEARISH"

    # --------------------------------------------------------
    # Simple CHoCH
    # --------------------------------------------------------

    if (
        previous["close"] < previous["open"]
        and
        last["close"] > previous["high"]
    ):

        choch = "BULLISH"

    elif (
        previous["close"] > previous["open"]
        and
        last["close"] < previous["low"]
    ):

        choch = "BEARISH"

    return {
        "bos": bos,
        "choch": choch,
        "sweep": sweep
    }


# ============================================================
# TIMEFRAME ENGINE
# ============================================================

def timeframe_analysis(
    interval
):

    candles = get_candles(
        interval,
        120
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

    current_rsi = rsi(
        closes,
        14
    )

    current_atr = atr(
        candles,
        14
    )

    last = candles[-1]

    bullish = (
        last["close"] >
        last["open"]
    )

    bearish = (
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

    st = structure(
        candles
    )

    return {
        "candles": candles,
        "price": last["close"],
        "ema20": ema20,
        "ema50": ema50,
        "rsi": current_rsi,
        "atr": current_atr,
        "trend": trend,
        "bullish": bullish,
        "bearish": bearish,
        "bos": st["bos"],
        "choch": st["choch"],
        "sweep": st["sweep"]
    }


# ============================================================
# V3 SIGNAL ENGINE
# ============================================================

def build_signal():

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
            "error": "Market data yetarli emas."
        }

    buy = 0
    sell = 0

    reasons_buy = []
    reasons_sell = []

    # ========================================================
    # 15M TREND
    # ========================================================

    if tf15["trend"] == "BULLISH":

        buy += 3

        reasons_buy.append(
            "15M bullish trend"
        )

    elif tf15["trend"] == "BEARISH":

        sell += 3

        reasons_sell.append(
            "15M bearish trend"
        )

    # ========================================================
    # 5M TREND
    # ========================================================

    if tf5["trend"] == "BULLISH":

        buy += 2

        reasons_buy.append(
            "5M bullish"
        )

    elif tf5["trend"] == "BEARISH":

        sell += 2

        reasons_sell.append(
            "5M bearish"
        )

    # ========================================================
    # 1M TREND
    # ========================================================

    if tf1["trend"] == "BULLISH":

        buy += 1

        reasons_buy.append(
            "1M bullish"
        )

    elif tf1["trend"] == "BEARISH":

        sell += 1

        reasons_sell.append(
            "1M bearish"
        )

    # ========================================================
    # RSI
    # ========================================================

    if 50 < tf5["rsi"] < 70:

        buy += 1

        reasons_buy.append(
            "5M RSI bullish zone"
        )

    elif 30 < tf5["rsi"] < 50:

        sell += 1

        reasons_sell.append(
            "5M RSI bearish zone"
        )

    if 50 < tf1["rsi"] < 70:

        buy += 1

        reasons_buy.append(
            "1M RSI bullish"
        )

    elif 30 < tf1["rsi"] < 50:

        sell += 1

        reasons_sell.append(
            "1M RSI bearish"
        )

    # ========================================================
    # BOS
    # ========================================================

    if tf5["bos"] == "BULLISH":

        buy += 2

        reasons_buy.append(
            "5M bullish BOS"
        )

    elif tf5["bos"] == "BEARISH":

        sell += 2

        reasons_sell.append(
            "5M bearish BOS"
        )

    if tf1["bos"] == "BULLISH":

        buy += 2

        reasons_buy.append(
            "1M bullish BOS"
        )

    elif tf1["bos"] == "BEARISH":

        sell += 2

        reasons_sell.append(
            "1M bearish BOS"
        )

    # ========================================================
    # CHoCH
    # ========================================================

    if tf1["choch"] == "BULLISH":

        buy += 2

        reasons_buy.append(
            "1M bullish CHoCH"
        )

    elif tf1["choch"] == "BEARISH":

        sell += 2

        reasons_sell.append(
            "1M bearish CHoCH"
        )

    # ========================================================
    # LIQUIDITY SWEEP
    # ========================================================

    if tf1["sweep"] == "BULLISH":

        buy += 2

        reasons_buy.append(
            "1M bullish liquidity sweep"
        )

    elif tf1["sweep"] == "BEARISH":

        sell += 2

        reasons_sell.append(
            "1M bearish liquidity sweep"
        )

    # ========================================================
    # CANDLE CONFIRMATION
    # ========================================================

    if tf1["bullish"]:

        buy += 1

        reasons_buy.append(
            "1M bullish candle"
        )

    elif tf1["bearish"]:

        sell += 1

        reasons_sell.append(
            "1M bearish candle"
        )

    # ========================================================
    # FINAL DECISION
    # ========================================================

    total = max(
        buy,
        sell
    )

    # Confidence is SCORE based,
    # NOT a claimed win probability.
    confidence = min(
        99,
        int(
            total /
            18 *
            100
        )
    )

    price = tf1["price"]

    current_atr = tf1["atr"]

    # --------------------------------------------------------
    # BUY
    # --------------------------------------------------------

    if (
        buy >= MIN_SCORE
        and
        buy > sell
    ):

        entry = price

        sl = (
            entry -
            current_atr *
            SL_ATR_MULTIPLIER
        )

        risk = (
            entry -
            sl
        )

        tp1 = (
            entry +
            risk *
            RR1
        )

        tp2 = (
            entry +
            risk *
            RR2
        )

        tp3 = (
            entry +
            risk *
            RR3
        )

        return {
            "signal": "BUY",
            "entry": entry,
            "sl": sl,
            "tp1": tp1,
            "tp2": tp2,
            "tp3": tp3,
            "confidence": confidence,
            "buy": buy,
            "sell": sell,
            "tf15": tf15,
            "tf5": tf5,
            "tf1": tf1,
            "reasons": reasons_buy
        }

    # --------------------------------------------------------
    # SELL
    # --------------------------------------------------------

    if (
        sell >= MIN_SCORE
        and
        sell > buy
    ):

        entry = price

        sl = (
            entry +
            current_atr *
            SL_ATR_MULTIPLIER
        )

        risk = (
            sl -
            entry
        )

        tp1 = (
            entry -
            risk *
            RR1
        )

        tp2 = (
            entry -
            risk *
            RR2
        )

        tp3 = (
            entry -
            risk *
            RR3
        )

        return {
            "signal": "SELL",
            "entry": entry,
            "sl": sl,
            "tp1": tp1,
            "tp2": tp2,
            "tp3": tp3,
            "confidence": confidence,
            "buy": buy,
            "sell": sell,
            "tf15": tf15,
            "tf5": tf5,
            "tf1": tf1,
            "reasons": reasons_sell
        }

    # --------------------------------------------------------
    # WAIT
    # --------------------------------------------------------

    return {
        "signal": "WAIT",
        "price": price,
        "confidence": confidence,
        "buy": buy,
        "sell": sell,
        "tf15": tf15,
        "tf5": tf5,
        "tf1": tf1
    }


# ============================================================
# SIGNAL MESSAGE
# ============================================================

def signal_message():

    result = build_signal()

    if result.get("error"):

        return (
            "❌ <b>V3 DATA ERROR</b>\n\n"
            f"{result['error']}"
        )

    tf15 = result["tf15"]
    tf5 = result["tf5"]
    tf1 = result["tf1"]

    # ========================================================
    # WAIT
    # ========================================================

    if result["signal"] == "WAIT":

        return (
            "🟡 <b>XAU/USD V3</b>\n\n"
            "⏳ <b>WAIT</b>\n\n"
            f"💰 Price: "
            f"<b>{result['price']:.2f}</b>\n\n"

            f"📊 15M: "
            f"<b>{tf15['trend']}</b>\n"

            f"📊 5M: "
            f"<b>{tf5['trend']}</b>\n"

            f"📊 1M: "
            f"<b>{tf1['trend']}</b>\n\n"

            f"📈 5M RSI: "
            f"<b>{tf5['rsi']:.1f}</b>\n"

            f"📉 1M RSI: "
            f"<b>{tf1['rsi']:.1f}</b>\n\n"

            f"🟢 Buy score: "
            f"<b>{result['buy']}</b>\n"

            f"🔴 Sell score: "
            f"<b>{result['sell']}</b>\n\n"

            f"🧠 Score confidence: "
            f"<b>{result['confidence']}%</b>\n\n"

            "❌ Kuchli entry confirmation yo‘q."
        )

    # ========================================================
    # BUY / SELL
    # ========================================================

    emoji = (
        "🟢"
        if result["signal"] == "BUY"
        else "🔴"
    )

    structure_text = (
        f"5M BOS: "
        f"<b>{tf5['bos']}</b>\n"
        f"1M BOS: "
        f"<b>{tf1['bos']}</b>\n"
        f"1M CHoCH: "
        f"<b>{tf1['choch']}</b>\n"
        f"1M Sweep: "
        f"<b>{tf1['sweep']}</b>"
    )

    reasons = result.get(
        "reasons",
        []
    )

    reason_text = "\n".join(
        f"• {r}"
        for r in reasons[:7]
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
        f"<b>{tf15['trend']}</b>\n"

        f"📊 5M: "
        f"<b>{tf5['trend']}</b>\n"

        f"📊 1M: "
        f"<b>{tf1['trend']}</b>\n\n"

        f"📈 5M RSI: "
        f"<b>{tf5['rsi']:.1f}</b>\n"

        f"📉 1M RSI: "
        f"<b>{tf1['rsi']:.1f}</b>\n\n"

        f"🧠 Score confidence: "
        f"<b>{result['confidence']}%</b>\n\n"

        "🔎 <b>STRUCTURE</b>\n"
        f"{structure_text}\n\n"

        "🧠 <b>CONFIRMATIONS</b>\n"
        f"{reason_text}\n\n"

        "⚠️ Confidence — score asosidagi "
        "texnik ko‘rsatkich. Bu kafolatlangan "
        "win-rate emas."
    )


# ============================================================
# MARKET ANALYSIS
# ============================================================

def market_analysis():

    tf15 = timeframe_analysis("15min")
    tf5 = timeframe_analysis("5min")
    tf1 = timeframe_analysis("1min")

    if not tf15 or not tf5 or not tf1:

        return (
            "❌ Market data yetarli emas."
        )

    return (
        "📈 <b>MARKET ANALYSIS V3</b>\n\n"

        f"🥇 Price: "
        f"<b>{tf1['price']:.2f}</b>\n\n"

        f"15M Trend: "
        f"<b>{tf15['trend']}</b>\n"
        f"5M Trend: "
        f"<b>{tf5['trend']}</b>\n"
        f"1M Trend: "
        f"<b>{tf1['trend']}</b>\n\n"

        f"5M RSI: "
        f"<b>{tf5['rsi']:.1f}</b>\n"
        f"1M RSI: "
        f"<b>{tf1['rsi']:.1f}</b>\n\n"

        "🔎 <b>STRUCTURE</b>\n"

        f"5M BOS: "
        f"<b>{tf5['bos']}</b>\n"

        f"1M BOS: "
        f"<b>{tf1['bos']}</b>\n"

        f"1M CHoCH: "
        f"<b>{tf1['choch']}</b>\n"

        f"1M Liquidity: "
        f"<b>{tf1['sweep']}</b>"
    )


# ============================================================
# AI ADVISOR
# ============================================================

def advisor():

    result = build_signal()

    if result.get("error"):

        return (
            "🤖 <b>AI ADVISOR</b>\n\n"
            "Market data yetarli emas."
        )

    if result["signal"] == "BUY":

        advice = (
            "🟢 Technical bias BUY.\n"
            "Entry faqat SL bilan ishlatilishi kerak."
        )

    elif result["signal"] == "SELL":

        advice = (
            "🔴 Technical bias SELL.\n"
            "Entry faqat SL bilan ishlatilishi kerak."
        )

    else:

        advice = (
            "🟡 Hozircha WAIT.\n"
            "Bozor confirmation bermadi."
        )

    return (
        "🤖 <b>BEGZOD AI ADVISOR V3</b>\n\n"
        f"🥇 Price: "
        f"<b>{result.get('price', result.get('entry', 0)):.2f}</b>\n\n"

        f"📊 15M: "
        f"<b>{result['tf15']['trend']}</b>\n"

        f"📊 5M: "
        f"<b>{result['tf5']['trend']}</b>\n"

        f"📊 1M: "
        f"<b>{result['tf1']['trend']}</b>\n\n"

        f"🧠 Score: "
        f"<b>{max(result['buy'], result['sell'])}</b>\n"

        f"Confidence: "
        f"<b>{result['confidence']}%</b>\n\n"

        f"{advice}\n\n"

        "⚠️ Bu avtomatik texnik analiz."
    )


# ============================================================
# SETTINGS
# ============================================================

def settings():

    return (
        "⚙️ <b>SETTINGS V3</b>\n\n"
        "Symbol: XAU/USD\n"
        "Timeframes: 15M / 5M / 1M\n"
        "SL: ATR × 1.20\n"
        "TP: 1R / 2R / 3R\n"
        "Minimum score: 8\n\n"
        "News engine hozircha V3 signaliga "
        "ta'sir qilmaydi."
    )


# ============================================================
# UPDATE HANDLER
# ============================================================

def process_update(update):

    try:

        if "message" not in update:

            return

        message = update["message"]

        chat_id = message[
            "chat"
        ]["id"]

        text = message.get(
            "text",
            ""
        ).strip()

        print(
            "Telegram message:",
            text
        )

        # ----------------------------------------------------
        # START
        # ----------------------------------------------------

        if text == "/start":

            start_message(
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
                    "📚 <b>COMMANDS</b>\n\n"
                    "/start\n"
                    "/price\n"
                    "/signal\n"
                    "/market\n"
                    "/advisor\n"
                    "/help"
                ),
                keyboard()
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
                "🔎 Live XAU/USD narxi olinmoqda..."
            )

            price = get_price()

            if price is None:

                send_message(
                    chat_id,
                    (
                        "❌ Narxni olishda xato.\n\n"
                        "Twelve Data API "
                        "tekshiring."
                    ),
                    keyboard()
                )

            else:

                send_message(
                    chat_id,
                    (
                        "🥇 <b>XAU/USD</b>\n\n"
                        f"💰 Live Price: "
                        f"<b>{price:.2f}</b>"
                    ),
                    keyboard()
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
                "🔎 V3 XAU/USD analiz qilinmoqda..."
            )

            try:

                result = signal_message()

                send_message(
                    chat_id,
                    result,
                    keyboard()
                )

            except Exception as e:

                print(
                    "Signal error:",
                    repr(e)
                )

                send_message(
                    chat_id,
                    (
                        "❌ Signal error.\n"
                        "Render Logsni tekshiring."
                    ),
                    keyboard()
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
                    market_analysis(),
                    keyboard()
                )

            except Exception as e:

                print(
                    "Market error:",
                    repr(e)
                )

                send_message(
                    chat_id,
                    "❌ Market analysis error.",
                    keyboard()
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
                "🤖 AI Advisor analiz qilmoqda..."
            )

            try:

                send_message(
                    chat_id,
                    advisor(),
                    keyboard()
                )

            except Exception as e:

                print(
                    "Advisor error:",
                    repr(e)
                )

                send_message(
                    chat_id,
                    "❌ Advisor error.",
                    keyboard()
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
                    "News engine keyingi modulda "
                    "kuchaytiriladi.\n\n"
                    "Hozircha V3 signal "
                    "technical analysisga asoslanadi."
                ),
                keyboard()
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
                    "📅 <b>NEWS</b>\n\n"
                    "News engine hozircha "
                    "mavjud ma'lumot bo‘lmasa "
                    "'News mavjud emas' deb "
                    "ko‘rsatadi.\n\n"
                    "V3 technical engine bunga "
                    "bog‘lanmagan."
                ),
                keyboard()
            )

            return

        # ----------------------------------------------------
        # SETTINGS
        # ----------------------------------------------------

        if text == "⚙️ Settings":

            send_message(
                chat_id,
                settings(),
                keyboard()
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
            keyboard()
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
            "Webhook:",
            result
        )

    except Exception as e:

        print(
            "Webhook error:",
            repr(e)
        )


# ============================================================
# TELEGRAM LOOP
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

            for update in data.get(
                "result",
                []
            ):

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
            b"BEGZOD AI XAUUSD V3.1 RUNNING"
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
        f"Health server running on {port}"
    )

    server.serve_forever()


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    print(
        "STARTING BEGZOD AI XAUUSD V3.1"
    )

    delete_webhook()

    threading.Thread(
        target=start_server,
        daemon=True
    ).start()

    telegram_loop()
  
