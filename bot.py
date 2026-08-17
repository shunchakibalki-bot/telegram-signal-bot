
import os
import time
import json
import threading
import requests

from http.server import BaseHTTPRequestHandler, HTTPServer


# ============================================================
# BEGZOD AI XAU/USD V4
# STRICT MULTI-TIMEFRAME SIGNAL ENGINE
# ============================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
TWELVE_API_KEY = os.getenv("TWELVE_API_KEY")

SYMBOL = "XAU/USD"

TELEGRAM_API = ""

if BOT_TOKEN:
    TELEGRAM_API = (
        "https://api.telegram.org/bot"
        + BOT_TOKEN
    )

TIMEOUT = 25

# Signal requirements
MIN_SCORE = 9

# ATR based risk
SL_ATR_MULTIPLIER = 1.20

# Do not allow excessively stretched 1M entries
RSI_BUY_MAX = 68.0
RSI_SELL_MIN = 32.0


# ============================================================
# STARTUP
# ============================================================

print("==========================================")
print("BEGZOD AI XAU/USD V4")
print("STRICT SIGNAL ENGINE")
print("==========================================")

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
            TELEGRAM_API + "/" + method,
            data=data or {},
            timeout=TIMEOUT
        )

        if not response.ok:

            print(
                "Telegram HTTP error:",
                response.status_code,
                response.text[:300]
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
    keyboard=True
):

    data = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }

    if keyboard:

        data["reply_markup"] = json.dumps(
            main_keyboard(),
            ensure_ascii=False
        )

    telegram_request(
        "sendMessage",
        data
    )


def main_keyboard():

    return {
        "keyboard": [
            [
                {
                    "text": "🥇 Live Price"
                },
                {
                    "text": "🎯 AI Signal"
                }
            ],
            [
                {
                    "text": "📊 Technical"
                },
                {
                    "text": "🧠 AI Advisor"
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
                    "text": "⚙️ Settings"
                }
            ]
        ],
        "resize_keyboard": True
    }


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

        request_params = {}

        if params:
            request_params.update(params)

        request_params["apikey"] = (
            TWELVE_API_KEY
        )

        url = (
            "https://api.twelvedata.com/"
            + endpoint
        )

        response = requests.get(
            url,
            params=request_params,
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
            "Twelve Data error:",
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

    except Exception:

        return None


# ============================================================
# CANDLES
# ============================================================

def get_candles(
    interval,
    outputsize=150
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
        2.0 /
        (period + 1.0)
    )

    result = (
        sum(values[:period]) /
        period
    )

    for value in values[period:]:

        result = (
            (value - result) *
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

            gains.append(change)
            losses.append(0.0)

        else:

            gains.append(0.0)
            losses.append(
                abs(change)
            )

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

    rs = (
        avg_gain /
        avg_loss
    )

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

        current = candles[i]
        previous = candles[i - 1]

        tr = max(
            current["high"]
            - current["low"],

            abs(
                current["high"]
                - previous["close"]
            ),

            abs(
                current["low"]
                - previous["close"]
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
# STRUCTURE
# ============================================================

def structure(
    candles
):

    result = {
        "bos": "NONE",
        "choch": "NONE",
        "sweep": "NONE"
    }

    if len(candles) < 20:
        return result

    last = candles[-1]
    previous = candles[-2]

    recent = candles[-12:-2]

    high = max(
        c["high"]
        for c in recent
    )

    low = min(
        c["low"]
        for c in recent
    )

    # --------------------------------------------------------
    # BOS
    # --------------------------------------------------------

    if last["close"] > high:

        result["bos"] = "BULLISH"

    elif last["close"] < low:

        result["bos"] = "BEARISH"

    # --------------------------------------------------------
    # LIQUIDITY SWEEP
    # --------------------------------------------------------

    if (
        last["low"] < low
        and
        last["close"] > low
    ):

        result["sweep"] = "BULLISH"

    elif (
        last["high"] > high
        and
        last["close"] < high
    ):

        result["sweep"] = "BEARISH"

    # --------------------------------------------------------
    # CHoCH
    # --------------------------------------------------------

    if (
        previous["close"]
        < previous["open"]
        and
        last["close"]
        > previous["high"]
    ):

        result["choch"] = "BULLISH"

    elif (
        previous["close"]
        > previous["open"]
        and
        last["close"]
        < previous["low"]
    ):

        result["choch"] = "BEARISH"

    return result


# ============================================================
# TIMEFRAME ANALYSIS
# ============================================================

def timeframe_analysis(
    interval
):

    candles = get_candles(
        interval,
        150
    )

    if len(candles) < 60:

        print(
            interval,
            "insufficient candles:",
            len(candles)
        )

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

    market_structure = structure(
        candles
    )

    trend = "NEUTRAL"

    if ema20 > ema50:

        trend = "BULLISH"

    elif ema20 < ema50:

        trend = "BEARISH"

    return {
        "price": last["close"],
        "ema20": ema20,
        "ema50": ema50,
        "rsi": current_rsi,
        "atr": current_atr,
        "trend": trend,
        "bos": market_structure["bos"],
        "choch": market_structure["choch"],
        "sweep": market_structure["sweep"],
        "bullish_candle": (
            last["close"] >
            last["open"]
        ),
        "bearish_candle": (
            last["close"] <
            last["open"]
        )
    }


# ============================================================
# V4 SIGNAL ENGINE
# ============================================================

def generate_signal():

    print(
        "V4 analysis started..."
    )

    tf15 = timeframe_analysis(
        "15min"
    )

    tf5 = timeframe_analysis(
        "5min"
    )

    tf1 = timeframe_analysis(
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
                "Market data yetarli emas."
            )
        }

    buy_score = 0
    sell_score = 0

    buy_reasons = []
    sell_reasons = []

    # ========================================================
    # 15M BIAS
    # ========================================================

    if tf15["trend"] == "BULLISH":

        buy_score += 3

        buy_reasons.append(
            "15M bullish bias"
        )

    elif tf15["trend"] == "BEARISH":

        sell_score += 3

        sell_reasons.append(
            "15M bearish bias"
        )

    # ========================================================
    # 5M SETUP
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

    # 5M BOS

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
    # 5M RSI
    # ========================================================

    if (
        50.0 <
        tf5["rsi"] <
        70.0
    ):

        buy_score += 1

        buy_reasons.append(
            "5M RSI bullish"
        )

    elif (
        30.0 <
        tf5["rsi"] <
        50.0
    ):

        sell_score += 1

        sell_reasons.append(
            "5M RSI bearish"
        )

    # ========================================================
    # 1M ENTRY
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
    # 1M BOS
    # ========================================================

    if tf1["bos"] == "BULLISH":

        buy_score += 3

        buy_reasons.append(
            "1M bullish BOS"
        )

    elif tf1["bos"] == "BEARISH":

        sell_score += 3

        sell_reasons.append(
            "1M bearish BOS"
        )

    # ========================================================
    # 1M CHOCH
    # ========================================================

    if tf1["choch"] == "BULLISH":

        buy_score += 3

        buy_reasons.append(
            "1M bullish CHoCH"
        )

    elif tf1["choch"] == "BEARISH":

        sell_score += 3

        sell_reasons.append(
            "1M bearish CHoCH"
        )

    # ========================================================
    # LIQUIDITY
    # ========================================================

    if tf1["sweep"] == "BULLISH":

        buy_score += 3

        buy_reasons.append(
            "1M bullish liquidity sweep"
        )

    elif tf1["sweep"] == "BEARISH":

        sell_score += 3

        sell_reasons.append(
            "1M bearish liquidity sweep"
        )

    # ========================================================
    # 1M RSI
    # ========================================================

    if (
        50.0 <
        tf1["rsi"] <
        RSI_BUY_MAX
    ):

        buy_score += 1

        buy_reasons.append(
            "1M RSI bullish"
        )

    elif (
        RSI_SELL_MIN <
        tf1["rsi"] <
        50.0
    ):

        sell_score += 1

        sell_reasons.append(
            "1M RSI bearish"
        )

    # ========================================================
    # MOMENTUM CANDLE
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
    # STRICT DIRECTION FILTER
    # ========================================================

    # BUY requires:
    #
    # 15M bullish
    # 5M bullish
    # 1M bullish
    #
    # AND
    #
    # 1M BOS OR CHoCH OR liquidity sweep

    buy_structure = (
        tf1["bos"] == "BULLISH"
        or
        tf1["choch"] == "BULLISH"
        or
        tf1["sweep"] == "BULLISH"
    )

    sell_structure = (
        tf1["bos"] == "BEARISH"
        or
        tf1["choch"] == "BEARISH"
        or
        tf1["sweep"] == "BEARISH"
    )

    buy_alignment = (
        tf15["trend"] == "BULLISH"
        and
        tf5["trend"] == "BULLISH"
        and
        tf1["trend"] == "BULLISH"
    )

    sell_alignment = (
        tf15["trend"] == "BEARISH"
        and
        tf5["trend"] == "BEARISH"
        and
        tf1["trend"] == "BEARISH"
    )

    # ========================================================
    # CONFIDENCE
    # ========================================================

    max_possible = 22

    best_score = max(
        buy_score,
        sell_score
    )

    confidence = int(
        min(
            99,
            (
                best_score /
                max_possible
            ) * 100
        )
    )

    # ========================================================
    # BUY
    # ========================================================

    if (
        buy_score >= MIN_SCORE
        and
        buy_score > sell_score
        and
        buy_alignment
        and
        buy_structure
        and
        tf1["rsi"] < RSI_BUY_MAX
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

        tp1 = (
            entry +
            risk
        )

        tp2 = (
            entry +
            risk * 2.0
        )

        tp3 = (
            entry +
            risk * 3.0
        )

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
        and
        sell_alignment
        and
        sell_structure
        and
        tf1["rsi"] > RSI_SELL_MIN
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

        tp1 = (
            entry -
            risk
        )

        tp2 = (
            entry -
            risk * 2.0
        )

        tp3 = (
            entry -
            risk * 3.0
        )

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
        "tf1": tf1,
        "buy_alignment": buy_alignment,
        "sell_alignment": sell_alignment,
        "buy_structure": buy_structure,
        "sell_structure": sell_structure
    }


# ============================================================
# SIGNAL MESSAGE
# ============================================================

def signal_message():

    result = generate_signal()

    if result.get("error"):

        return (
            "❌ <b>DATA ERROR</b>\n\n"
            + result["error"]
        )

    tf15 = result["tf15"]
    tf5 = result["tf5"]
    tf1 = result["tf1"]

    # ========================================================
    # WAIT
    # ========================================================

    if result["signal"] == "WAIT":

        return (
            "🟡 <b>XAU/USD V4</b>\n\n"

            "⏳ <b>WAIT</b>\n\n"

            "💰 Price: "
            f"<b>{result['price']:.2f}</b>\n\n"

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

            "🟢 Buy score: "
            f"<b>{result['buy_score']}</b>\n"

            "🔴 Sell score: "
            f"<b>{result['sell_score']}</b>\n\n"

            "🧠 Confidence: "
            f"<b>{result['confidence']}%</b>\n\n"

            "🔒 <b>ENTRY FILTER</b>\n"

            "BUY alignment: "
            f"<b>{'YES' if result['buy_alignment'] else 'NO'}</b>\n"

            "SELL alignment: "
            f"<b>{'YES' if result['sell_alignment'] else 'NO'}</b>\n\n"

            "❌ Kuchli entry tasdig‘i "
            "yo‘q.\n\n"

            "V4 1M confirmation bo‘lmasa "
            "signal bermaydi."
        )

    # ========================================================
    # BUY / SELL
    # ========================================================

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

    for reason in reasons[:10]:

        reason_text += (
            "• "
            + reason
            + "\n"
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

        "🧠 Confidence: "
        f"<b>{result['confidence']}%</b>\n\n"

        "✅ <b>CONFIRMATIONS</b>\n"
        + reason_text +

        "\n⚠️ Confidence win-rate "
        "kafolati emas."
    )


# ============================================================
# TECHNICAL ANALYSIS
# ============================================================

def technical_message():

    tf15 = timeframe_analysis(
        "15min"
    )

    tf5 = timeframe_analysis(
        "5min"
    )

    tf1 = timeframe_analysis(
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
            "❌ Technical data yetarli emas."
        )

    return (
        "📊 <b>TECHNICAL ANALYSIS</b>\n\n"

        "🥇 Price: "
        f"<b>{tf1['price']:.2f}</b>\n\n"

        "15M Trend: "
        f"<b>{tf15['trend']}</b>\n"

        "5M Trend: "
        f"<b>{tf5['trend']}</b>\n"

        "1M Trend: "
        f"<b>{tf1['trend']}</b>\n\n"

        "5M RSI: "
        f"<b>{tf5['rsi']:.1f}</b>\n"

        "1M RSI: "
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

        "ATR 1M: "
        f"<b>{tf1['atr']:.2f}</b>"
    )


# ============================================================
# AI ADVISOR
# ============================================================

def advisor_message():

    result = generate_signal()

    if result.get("error"):

        return (
            "🤖 <b>AI ADVISOR</b>\n\n"
            "❌ Data yetarli emas."
        )

    tf15 = result["tf15"]
    tf5 = result["tf5"]
    tf1 = result["tf1"]

    if result["signal"] == "BUY":

        advice = (
            "🟢 BUY setup tasdiqlangan.\n"
            "Entry faqat ko‘rsatilgan "
            "SL bilan ko‘rib chiqiladi."
        )

    elif result["signal"] == "SELL":

        advice = (
            "🔴 SELL setup tasdiqlangan.\n"
            "Entry faqat ko‘rsatilgan "
            "SL bilan ko‘rib chiqiladi."
        )

    else:

        advice = (
            "🟡 HOZIR WAIT.\n\n"
            "15M/5M/1M alignment yoki "
            "1M structure confirmation "
            "yetishmayapti.\n\n"
            "Bozorni quvib entry qilmaslik."
        )

    return (
        "🤖 <b>BEGZOD AI ADVISOR V4</b>\n\n"

        "🥇 Price: "
        f"<b>{tf1['price']:.2f}</b>\n\n"

        "15M: "
        f"<b>{tf15['trend']}</b>\n"

        "5M: "
        f"<b>{tf5['trend']}</b>\n"

        "1M: "
        f"<b>{tf1['trend']}</b>\n\n"

        "📌 <b>ADVICE</b>\n"
        f"{advice}\n\n"

        "⚠️ Bu avtomatik texnik "
        "tahlil. Kafolatlangan natija emas."
    )


# ============================================================
# FUNDAMENTAL
# ============================================================

def fundamental_message():

    return (
        "📰 <b>FUNDAMENTAL ANALYSIS</b>\n\n"

        "Hozircha fundamental modul "
        "signalga ulanmagan.\n\n"

        "Keyingi bosqichda:\n"

        "• CPI\n"
        "• NFP\n"
        "• FOMC\n"
        "• Fed\n"
        "• PCE\n"
        "• GDP\n"
        "• USD news\n\n"

        "qo‘shilib, signalga "
        "News Risk filtri ulanadi."
    )


# ============================================================
# NEWS
# ============================================================

def news_message():

    return (
        "📅 <b>MARKET NEWS</b>\n\n"

        "News provider hali "
        "signal engine'ga ulanmagan.\n\n"

        "⚠️ Keyingi V5 bosqichida "
        "high-impact news filtri "
        "qo‘shiladi."
    )


# ============================================================
# START
# ============================================================

def start_message(chat_id):

    send_message(
        chat_id,
        (
            "🤖 <b>BEGZOD AI XAU/USD V4</b>\n\n"

            "🥇 Real-time XAU/USD\n"
            "📊 15M + 5M + 1M\n"
            "📐 BOS / CHoCH\n"
            "💧 Liquidity\n"
            "🎯 Strict Entry Filter\n"
            "🛑 Dynamic SL\n"
            "💰 TP1 / TP2 / TP3\n\n"

            "👇 Bo‘limni tanlang."
        )
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

        # START

        if text == "/start":

            start_message(
                chat_id
            )

            return

        # HELP

        if text == "/help":

            send_message(
                chat_id,
                (
                    "📚 <b>HELP</b>\n\n"

                    "/start\n"
                    "/price\n"
                    "/signal\n"
                    "/technical\n"
                    "/advisor\n"
                    "/fundamental\n"
                    "/news"
                )
            )

            return

        # PRICE

        if text in (
            "/price",
            "🥇 Live Price"
        ):

            send_message(
                chat_id,
                "🔎 Live price olinmoqda...",
                False
            )

            price = get_live_price()

            if price is None:

                send_message(
                    chat_id,
                    "❌ Live price olinmadi."
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

        # SIGNAL

        if text in (
            "/signal",
            "🎯 AI Signal"
        ):

            send_message(
                chat_id,
                "🔎 V4 signal analiz qilinmoqda...",
                False
            )

            try:

                result = signal_message()

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
                    "❌ Signal analysis error."
                )

            return

        # TECHNICAL

        if text in (
            "/technical",
            "📊 Technical"
        ):

            send_message(
                chat_id,
                "📊 Technical analysis...",
                False
            )

            try:

                result = technical_message()

                send_message(
                    chat_id,
                    result
                )

            except Exception as e:

                print(
                    "TECH ERROR:",
                    repr(e)
                )

                send_message(
                    chat_id,
                    "❌ Technical analysis error."
                )

            return

        # ADVISOR

        if text in (
            "/advisor",
            "🧠 AI Advisor"
        ):

            send_message(
                chat_id,
                "🧠 AI Advisor...",
                False
            )

            try:

                result = advisor_message()

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
                    "❌ Advisor error."
                )

            return

        # FUNDAMENTAL

        if text in (
            "/fundamental",
            "📰 Fundamental"
        ):

            send_message(
                chat_id,
                fundamental_message()
            )

            return

        # NEWS

        if text in (
            "/news",
            "📅 News"
        ):

            send_message(
                chat_id,
                news_message()
            )

            return

        # SETTINGS

        if text == "⚙️ Settings":

            send_message(
                chat_id,
                (
                    "⚙️ <b>SETTINGS</b>\n\n"

                    "Symbol: XAU/USD\n"
                    "TF: 15M / 5M / 1M\n"
                    "SL: ATR × 1.20\n"
                    "TP: 1R / 2R / 3R\n"
                    "Min Score: 9\n"
                    "1M confirmation: REQUIRED"
                )
            )

            return

        # UNKNOWN

        send_message(
            chat_id,
            (
                "❓ Buyruq topilmadi.\n\n"
                "👇 Menyudan foydalaning."
            )
        )

    except Exception as e:

        print(
            "PROCESS UPDATE ERROR:",
            repr(e)
        )


# ============================================================
# WEBHOOK RESET
# ============================================================

def delete_webhook():

    if not BOT_TOKEN:
        return

    try:

        telegram_request(
            "deleteWebhook",
            {
                "drop_pending_updates": "true"
            }
        )

        print(
            "Webhook reset complete."
        )

    except Exception as e:

        print(
            "Webhook reset error:",
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

            for update in data.get(
                "result",
                []
            ):

                offset = (
                    update["update_id"]
                    + 1
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
            b"BEGZOD AI XAUUSD V4 RUNNING"
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
        "Health server running:",
        port
    )

    server.serve_forever()


# ============================================================
# MAIN
# ============================================================

def main():

    print(
        "Starting BEGZOD AI XAUUSD V4..."
    )

    if not BOT_TOKEN:

        print(
            "ERROR: BOT_TOKEN missing"
        )

    if not TWELVE_API_KEY:

        print(
            "ERROR: TWELVE_API_KEY missing"
        )

    if BOT_TOKEN:

        delete_webhook()

    threading.Thread(
        target=start_server,
        daemon=True
    ).start()

    if not BOT_TOKEN:

        while True:

            time.sleep(60)

    telegram_loop()


if __name__ == "__main__":

    main()
