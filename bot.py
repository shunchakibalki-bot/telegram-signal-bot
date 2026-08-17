import os
import time
import threading
import requests
from http.server import BaseHTTPRequestHandler, HTTPServer

# =========================================================
# CONFIG
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
TWELVE_API_KEY = os.getenv("TWELVE_API_KEY")
ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY", "")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN topilmadi")

if not TWELVE_API_KEY:
    raise RuntimeError("TWELVE_API_KEY topilmadi")

TELEGRAM_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
TWELVE_URL = "https://api.twelvedata.com/time_series"
ALPHA_URL = "https://www.alphavantage.co/query"

SYMBOL = "XAU/USD"


# =========================================================
# TELEGRAM
# =========================================================

def send_message(chat_id, text):
    try:
        r = requests.post(
            f"{TELEGRAM_URL}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML"
            },
            timeout=20
        )

        if not r.ok:
            print("Telegram error:", r.text)

    except Exception as e:
        print("Telegram exception:", e)


def send_menu(chat_id):
    keyboard = {
        "keyboard": [
            [{"text": "🥇 Narx"}, {"text": "🎯 Signal"}],
            [{"text": "📰 Fundamental"}, {"text": "🤖 AI Maslahat"}],
            [{"text": "ℹ️ Yordam"}]
        ],
        "resize_keyboard": True
    }

    try:
        requests.post(
            f"{TELEGRAM_URL}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": (
                    "🤖 <b>BEGZOD AI XAU/USD V5</b>\n\n"
                    "Real-time XAU/USD AI analiz."
                ),
                "parse_mode": "HTML",
                "reply_markup": keyboard
            },
            timeout=20
        )
    except Exception as e:
        print("Menu error:", e)


# =========================================================
# TWELVE DATA
# =========================================================

def get_candles(interval, outputsize=150):
    try:
        params = {
            "symbol": SYMBOL,
            "interval": interval,
            "outputsize": outputsize,
            "apikey": TWELVE_API_KEY
        }

        response = requests.get(
            TWELVE_URL,
            params=params,
            timeout=20
        )

        data = response.json()

        print(
            f"Twelve Data {interval}: "
            f"HTTP={response.status_code}"
        )

        if data.get("status") == "error":
            raise RuntimeError(
                data.get("message", "Twelve Data error")
            )

        values = data.get("values")

        if not values:
            raise RuntimeError(
                f"{interval} uchun candle ma'lumoti kelmadi"
            )

        candles = []

        for item in reversed(values):
            try:
                candles.append({
                    "time": item.get("datetime"),
                    "open": float(item["open"]),
                    "high": float(item["high"]),
                    "low": float(item["low"]),
                    "close": float(item["close"]),
                    "volume": float(item.get("volume") or 0)
                })
            except Exception:
                continue

        if len(candles) < 60:
            raise RuntimeError(
                f"{interval}: faqat {len(candles)} candle keldi"
            )

        return candles

    except Exception as e:
        print(f"Market data error {interval}:", e)
        raise


def get_current_price():
    candles = get_candles("1min", 5)
    return candles[-1]["close"]


# =========================================================
# INDICATORS
# =========================================================

def ema(values, period):
    if len(values) < period:
        return None

    multiplier = 2 / (period + 1)

    result = sum(values[:period]) / period

    for price in values[period:]:
        result = (
            (price - result) * multiplier
            + result
        )

    return result


def rsi(values, period=14):
    if len(values) < period + 1:
        return 50.0

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
        avg_gain = (
            (avg_gain * (period - 1))
            + gains[i]
        ) / period

        avg_loss = (
            (avg_loss * (period - 1))
            + losses[i]
        ) / period

    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss

    return 100 - (100 / (1 + rs))


def atr(candles, period=14):
    if len(candles) < period + 1:
        return 1.0

    trs = []

    for i in range(1, len(candles)):
        high = candles[i]["high"]
        low = candles[i]["low"]
        previous_close = candles[i - 1]["close"]

        tr = max(
            high - low,
            abs(high - previous_close),
            abs(low - previous_close)
        )

        trs.append(tr)

    return sum(trs[-period:]) / period


# =========================================================
# TREND
# =========================================================

def get_trend(candles):
    closes = [x["close"] for x in candles]

    e20 = ema(closes, 20)
    e50 = ema(closes, 50)

    if e20 is None or e50 is None:
        return "NEUTRAL", e20, e50

    if e20 > e50:
        return "BULLISH", e20, e50

    if e20 < e50:
        return "BEARISH", e20, e50

    return "NEUTRAL", e20, e50


# =========================================================
# MARKET STRUCTURE
# =========================================================

def structure(candles):
    if len(candles) < 10:
        return {
            "bos": "NONE",
            "choch": "NONE",
            "liquidity": "NONE"
        }

    last = candles[-1]
    prev = candles[-2]

    recent = candles[-7:-2]

    recent_high = max(x["high"] for x in recent)
    recent_low = min(x["low"] for x in recent)

    bos = "NONE"
    choch = "NONE"
    liquidity = "NONE"

    if last["close"] > recent_high:
        bos = "BULLISH"

    elif last["close"] < recent_low:
        bos = "BEARISH"

    if prev["close"] < recent_low and last["close"] > recent_high:
        choch = "BULLISH"

    elif prev["close"] > recent_high and last["close"] < recent_low:
        choch = "BEARISH"

    if last["high"] > recent_high and last["close"] < recent_high:
        liquidity = "SELL-SIDE LIQUIDITY"

    elif last["low"] < recent_low and last["close"] > recent_low:
        liquidity = "BUY-SIDE LIQUIDITY"

    return {
        "bos": bos,
        "choch": choch,
        "liquidity": liquidity
    }


# =========================================================
# FUNDAMENTAL
# =========================================================

def alpha_indicator(function):
    if not ALPHA_VANTAGE_API_KEY:
        return None

    try:
        params = {
            "function": function,
            "apikey": ALPHA_VANTAGE_API_KEY
        }

        r = requests.get(
            ALPHA_URL,
            params=params,
            timeout=20
        )

        data = r.json()

        if "Note" in data:
            print("Alpha Vantage limit:", data["Note"])
            return None

        if "Information" in data:
            print("Alpha Vantage info:", data["Information"])
            return None

        return data

    except Exception as e:
        print("Fundamental error:", e)
        return None


def fundamental_analysis():
    if not ALPHA_VANTAGE_API_KEY:
        return {
            "bias": "UNAVAILABLE",
            "gold": "NEUTRAL",
            "news_risk": "UNKNOWN",
            "cpi": "N/A",
            "nfp": "N/A",
            "fed": "N/A"
        }

    cpi_data = alpha_indicator("CPI")
    nfp_data = alpha_indicator("NONFARM_PAYROLL")
    fed_data = alpha_indicator("FEDERAL_FUNDS_RATE")

    values = []

    for dataset in [cpi_data, nfp_data, fed_data]:
        if isinstance(dataset, dict):
            for key, value in dataset.items():
                if isinstance(value, list):
                    values.extend(value)

    bias = "NEUTRAL"

    # Bu yerda fundamental biasni konservativ usulda baholaymiz.
    # Yetarli ma'lumot bo'lmasa BUY/SELL majburan berilmaydi.

    if len(values) >= 2:
        bias = "NEUTRAL"

    return {
        "bias": bias,
        "gold": (
            "NEUTRAL"
            if bias == "NEUTRAL"
            else "BUY"
        ),
        "news_risk": "CHECK NEWS",
        "cpi": "AVAILABLE" if cpi_data else "N/A",
        "nfp": "AVAILABLE" if nfp_data else "N/A",
        "fed": "AVAILABLE" if fed_data else "N/A"
    }


# =========================================================
# SIGNAL ENGINE
# =========================================================

def generate_signal():

    candles_15 = get_candles("15min", 150)
    candles_5 = get_candles("5min", 150)
    candles_1 = get_candles("1min", 150)

    trend15, ema15_20, ema15_50 = get_trend(candles_15)
    trend5, ema5_20, ema5_50 = get_trend(candles_5)
    trend1, ema1_20, ema1_50 = get_trend(candles_1)

    close5 = [x["close"] for x in candles_5]
    close1 = [x["close"] for x in candles_1]

    rsi5 = rsi(close5, 14)
    rsi1 = rsi(close1, 14)

    atr1 = atr(candles_1, 14)

    s5 = structure(candles_5)
    s1 = structure(candles_1)

    price = candles_1[-1]["close"]
    last1 = candles_1[-1]

    buy = 0
    sell = 0

    confirmations_buy = []
    confirmations_sell = []

    # 15M TREND
    if trend15 == "BULLISH":
        buy += 2
        confirmations_buy.append("15M bullish trend")

    elif trend15 == "BEARISH":
        sell += 2
        confirmations_sell.append("15M bearish trend")

    # 5M TREND
    if trend5 == "BULLISH":
        buy += 2
        confirmations_buy.append("5M bullish trend")

    elif trend5 == "BEARISH":
        sell += 2
        confirmations_sell.append("5M bearish trend")

    # 1M TREND
    if trend1 == "BULLISH":
        buy += 1

    elif trend1 == "BEARISH":
        sell += 1

    # RSI
    if 50 <= rsi5 <= 68:
        buy += 1
        confirmations_buy.append("5M RSI bullish")

    elif 32 <= rsi5 < 50:
        sell += 1
        confirmations_sell.append("5M RSI bearish")

    if 50 <= rsi1 <= 68:
        buy += 1
        confirmations_buy.append("1M RSI bullish")

    elif 32 <= rsi1 < 50:
        sell += 1
        confirmations_sell.append("1M RSI bearish")

    # CANDLE
    if last1["close"] > last1["open"]:
        buy += 1
        confirmations_buy.append("1M bullish candle")

    elif last1["close"] < last1["open"]:
        sell += 1
        confirmations_sell.append("1M bearish candle")

    # BOS
    if s5["bos"] == "BULLISH":
        buy += 2
        confirmations_buy.append("5M bullish BOS")

    elif s5["bos"] == "BEARISH":
        sell += 2
        confirmations_sell.append("5M bearish BOS")

    if s1["bos"] == "BULLISH":
        buy += 1
        confirmations_buy.append("1M bullish BOS")

    elif s1["bos"] == "BEARISH":
        sell += 1
        confirmations_sell.append("1M bearish BOS")

    # CHOCH
    if s1["choch"] == "BULLISH":
        buy += 2
        confirmations_buy.append("1M bullish CHoCH")

    elif s1["choch"] == "BEARISH":
        sell += 2
        confirmations_sell.append("1M bearish CHoCH")

    fundamental = fundamental_analysis()

    # Fundamental only as a small filter.
    if fundamental["bias"] == "BULLISH":
        buy += 1

    elif fundamental["bias"] == "BEARISH":
        sell += 1

    max_score = 13

    if buy > sell and buy >= 7:

        entry = price

        # Gold uchun ATR asosida dynamic SL
        sl_distance = max(
            atr1 * 1.2,
            0.80
        )

        sl = entry - sl_distance

        risk = entry - sl

        tp1 = entry + risk
        tp2 = entry + risk * 2
        tp3 = entry + risk * 3

        confidence = min(
            95,
            int(
                45 +
                (buy / max_score) * 50
            )
        )

        return {
            "signal": "BUY",
            "entry": entry,
            "sl": sl,
            "tp1": tp1,
            "tp2": tp2,
            "tp3": tp3,
            "trend15": trend15,
            "trend5": trend5,
            "trend1": trend1,
            "rsi5": rsi5,
            "rsi1": rsi1,
            "s5": s5,
            "s1": s1,
            "buy": buy,
            "sell": sell,
            "confidence": confidence,
            "confirmations": confirmations_buy,
            "fundamental": fundamental
        }

    if sell > buy and sell >= 7:

        entry = price

        sl_distance = max(
            atr1 * 1.2,
            0.80
        )

        sl = entry + sl_distance

        risk = sl - entry

        tp1 = entry - risk
        tp2 = entry - risk * 2
        tp3 = entry - risk * 3

        confidence = min(
            95,
            int(
                45 +
                (sell / max_score) * 50
            )
        )

        return {
            "signal": "SELL",
            "entry": entry,
            "sl": sl,
            "tp1": tp1,
            "tp2": tp2,
            "tp3": tp3,
            "trend15": trend15,
            "trend5": trend5,
            "trend1": trend1,
            "rsi5": rsi5,
            "rsi1": rsi1,
            "s5": s5,
            "s1": s1,
            "buy": buy,
            "sell": sell,
            "confidence": confidence,
            "confirmations": confirmations_sell,
            "fundamental": fundamental
        }

    return {
        "signal": "WAIT",
        "entry": price,
        "trend15": trend15,
        "trend5": trend5,
        "trend1": trend1,
        "rsi5": rsi5,
        "rsi1": rsi1,
        "s5": s5,
        "s1": s1,
        "buy": buy,
        "sell": sell,
        "confidence": 0,
        "confirmations": [],
        "fundamental": fundamental
    }


# =========================================================
# SIGNAL MESSAGE
# =========================================================

def signal_message():

    try:
        data = generate_signal()

    except Exception as e:
        return (
            "❌ <b>DATA ERROR</b>\n\n"
            f"Market data olishda xatolik:\n"
            f"<code>{str(e)}</code>\n\n"
            "Twelve Data API key va XAU/USD accessni tekshiring."
        )

    if data["signal"] == "WAIT":

        return (
            "🟡 <b>XAU/USD</b>\n\n"
            "⏳ <b>WAIT</b>\n\n"
            f"💰 Price: <b>{data['entry']:.2f}</b>\n\n"
            f"📊 15M Trend: <b>{data['trend15']}</b>\n"
            f"📊 5M Trend: <b>{data['trend5']}</b>\n"
            f"📊 1M Trend: <b>{data['trend1']}</b>\n\n"
            f"📈 5M RSI: <b>{data['rsi5']:.1f}</b>\n"
            f"📉 1M RSI: <b>{data['rsi1']:.1f}</b>\n\n"
            "🔎 <b>STRUCTURE</b>\n"
            f"5M BOS: {data['s5']['bos']}\n"
            f"1M BOS: {data['s1']['bos']}\n"
            f"1M CHoCH: {data['s1']['choch']}\n"
            f"1M Liquidity: {data['s1']['liquidity']}\n\n"
            f"🟢 Buy score: <b>{data['buy']}</b>\n"
            f"🔴 Sell score: <b>{data['sell']}</b>\n\n"
            "❌ Kuchli entry tasdig'i yo'q."
        )

    emoji = "🟢" if data["signal"] == "BUY" else "🔴"

    confirmations = "\n".join(
        f"• {x}"
        for x in data["confirmations"][:6]
    )

    return (
        f"{emoji} <b>XAU/USD {data['signal']}</b>\n\n"
        f"🎯 Entry: <b>{data['entry']:.2f}</b>\n"
        f"🛑 Stop Loss: <b>{data['sl']:.2f}</b>\n\n"
        f"💰 TP1: <b>{data['tp1']:.2f}</b>\n"
        f"💰 TP2: <b>{data['tp2']:.2f}</b>\n"
        f"💰 TP3: <b>{data['tp3']:.2f}</b>\n\n"
        f"📊 15M: <b>{data['trend15']}</b>\n"
        f"📊 5M: <b>{data['trend5']}</b>\n"
        f"📊 1M: <b>{data['trend1']}</b>\n\n"
        f"📈 5M RSI: <b>{data['rsi5']:.1f}</b>\n"
        f"📉 1M RSI: <b>{data['rsi1']:.1f}</b>\n\n"
        "🔎 <b>STRUCTURE</b>\n"
        f"5M BOS: {data['s5']['bos']}\n"
        f"1M BOS: {data['s1']['bos']}\n"
        f"1M CHoCH: {data['s1']['choch']}\n"
        f"1M Liquidity: {data['s1']['liquidity']}\n\n"
        f"🧠 Confidence: <b>{data['confidence']}%</b>\n\n"
        "✅ <b>CONFIRMATIONS</b>\n"
        f"{confirmations}\n\n"
        "⚠️ Bu texnik AI score. Kafolatlangan win-rate emas."
    )


# =========================================================
# PRICE
# =========================================================

def price_message():

    try:
        price = get_current_price()

        return (
            "🥇 <b>XAU/USD</b>\n\n"
            f"💰 Current price: <b>{price:.2f}</b>\n\n"
            "🟢 Real-time market data"
        )

    except Exception as e:

        return (
            "❌ <b>PRICE ERROR</b>\n\n"
            f"<code>{str(e)}</code>"
        )


# =========================================================
# FUNDAMENTAL MESSAGE
# =========================================================

def fundamental_message():

    data = fundamental_analysis()

    if data["bias"] == "UNAVAILABLE":

        return (
            "📰 <b>FUNDAMENTAL ANALYSIS</b>\n\n"
            "⚠️ Fundamental API ulanmagan.\n\n"
            "ALPHA_VANTAGE_API_KEY Render Environment'da "
            "bo'lishi kerak."
        )

    return (
        "📰 <b>FUNDAMENTAL ANALYSIS</b>\n\n"
        f"🇺🇸 USD Bias: <b>{data['bias']}</b>\n"
        f"🥇 XAU/USD Bias: <b>{data['gold']}</b>\n\n"
        f"📊 CPI: {data['cpi']}\n"
        f"👷 NFP: {data['nfp']}\n"
        f"🏦 Fed Rate: {data['fed']}\n\n"
        f"⚠️ News Risk: <b>{data['news_risk']}</b>\n\n"
        "Fundamental ma'lumotlar signalga "
        "qo'shimcha filtr sifatida ishlatiladi."
    )


# =========================================================
# AI ADVISOR
# =========================================================

def advisor_message():

    try:
        data = generate_signal()

        if data["signal"] == "BUY":

            advice = (
                "🟢 BUY tomonda texnik ustunlik bor.\n\n"
                "Lekin 1M structure tasdig'i zaif bo'lsa, "
                "darhol kirishdan ko'ra retest kutish xavfsizroq."
            )

        elif data["signal"] == "SELL":

            advice = (
                "🔴 SELL tomonda texnik ustunlik bor.\n\n"
                "Entry oldidan 1M confirmation va retest "
                "kutish ma'qul."
            )

        else:

            advice = (
                "🟡 Hozircha WAIT.\n\n"
                "Bozor yo'nalishi yetarlicha tasdiqlanmagan. "
                "Signalni majburan olish kerak emas."
            )

        return (
            "🤖 <b>AI MASLAHAT</b>\n\n"
            f"{advice}\n\n"
            f"15M: {data['trend15']}\n"
            f"5M: {data['trend5']}\n"
            f"1M: {data['trend1']}\n"
            f"5M RSI: {data['rsi5']:.1f}\n"
            f"1M RSI: {data['rsi1']:.1f}"
        )

    except Exception as e:

        return (
            "❌ AI maslahat uchun market data yetarli emas.\n\n"
            f"<code>{str(e)}</code>"
        )


# =========================================================
# HELP
# =========================================================

def help_message():

    return (
        "ℹ️ <b>BEGZOD AI XAU/USD</b>\n\n"
        "🥇 /price — real-time narx\n"
        "🎯 /signal — AI texnik signal\n"
        "📰 /fundamental — fundamental analiz\n"
        "🤖 /advice — AI maslahat\n"
        "ℹ️ /help — yordam\n\n"
        "Analiz: 15M + 5M + 1M."
    )


# =========================================================
# TELEGRAM UPDATE
# =========================================================

def process_update(update):

    if "message" not in update:
        return

    message = update["message"]

    chat_id = message["chat"]["id"]

    text = message.get("text", "").strip()

    if text == "/start":

        send_menu(chat_id)
        return

    if text in ["/price", "🥇 Narx"]:

        send_message(
            chat_id,
            price_message()
        )
        return

    if text in ["/signal", "🎯 Signal"]:

        send_message(
            chat_id,
            "🔎 <b>XAU/USD analiz qilinmoqda...</b>"
        )

        send_message(
            chat_id,
            signal_message()
        )
        return

    if text in ["/fundamental", "📰 Fundamental"]:

        send_message(
            chat_id,
            "📰 <b>Fundamental ma'lumot olinmoqda...</b>"
        )

        send_message(
            chat_id,
            fundamental_message()
        )
        return

    if text in ["/advice", "🤖 AI Maslahat"]:

        send_message(
            chat_id,
            advisor_message()
        )
        return

    if text in ["/help", "ℹ️ Yordam"]:

        send_message(
            chat_id,
            help_message()
        )
        return


# =========================================================
# TELEGRAM LOOP
# =========================================================

def telegram_loop():

    offset = None

    print("Telegram polling started.")

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
                print("Telegram API:", data)
                time.sleep(5)
                continue

            for update in data.get("result", []):

                offset = update["update_id"] + 1

                try:
                    process_update(update)
                except Exception as e:
                    print("Update error:", e)

        except Exception as e:

            print("Polling error:", e)

            time.sleep(5)


# =========================================================
# RENDER HEALTH SERVER
# =========================================================

class HealthHandler(BaseHTTPRequestHandler):

    def do_GET(self):

        self.send_response(200)

        self.send_header(
            "Content-Type",
            "text/plain; charset=utf-8"
        )

        self.end_headers()

        self.wfile.write(
            b"BEGZOD AI XAU/USD V5 is running!"
        )

    def log_message(self, format, *args):
        return


def start_server():

    port = int(
        os.environ.get("PORT", "10000")
    )

    server = HTTPServer(
        ("0.0.0.0", port),
        HealthHandler
    )

    print(
        f"Health server running on port {port}"
    )

    server.serve_forever()


# =========================================================
# START
# =========================================================

if __name__ == "__main__":

    print("=" * 50)
    print("BEGZOD AI XAU/USD V5")
    print("=" * 50)

    threading.Thread(
        target=start_server,
        daemon=True
    ).start()

    telegram_loop()
