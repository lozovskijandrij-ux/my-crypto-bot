import telebot, ccxt, time, pandas as pd, threading, sys
from google import genai

# --- ТВОЇ ДАНІ ---
TG_TOKEN = "8674374290:AAH08kkDCqL7GqOFOgQHnrAPnouXVCBJ-hE"
GEMINI_KEY = "AIzaSyAXRR_0Zyhacaux6SiyTr6czGjFId3R8F0"
CHAT_ID = "682352228"

try:
    client = genai.Client(api_key=GEMINI_KEY)
    MODEL = "gemini-3-flash-preview"
    SYS = "Ти про-трейдер. Пиши коротко, по суті, мова: Українська."
except: sys.exit(1)

bot = telebot.TeleBot(TG_TOKEN, threaded=False)
ex = ccxt.binance({'enableRateLimit': True})

def get_data(tf='5m'):
    try:
        b = ex.fetch_ohlcv('BTC/USDT', timeframe=tf, limit=50)
        df = pd.DataFrame(b, columns=['t', 'o', 'h', 'l', 'c', 'v'])
        diff = df['c'].diff()
        g = diff.where(diff > 0, 0).rolling(14).mean()
        l = -diff.where(diff < 0, 0).rolling(14).mean()
        rsi = 100 - (100 / (1 + (g.iloc[-1] / l.iloc[-1])))
        return rsi, df['c'].iloc[-1]
    except: return None, None

@bot.message_handler(commands=['analysis', 'now', 'trend'])
def handle_commands(m):
    rsi, p = get_data()
    if rsi:
        l_l, l_s = p * 0.952, p * 1.048
        prompt = f"{SYS}\nBTC:{p}, RSI:{rsi:.1f}. Порада для 20х."
        try:
            res = client.models.generate_content(model=MODEL, contents=prompt)
            bot.reply_to(m, f"📊 **BTC**: {p}$\n📈 **RSI**: {rsi:.1f}\n💀 Liq: {l_l:.0f}/{l_s:.0f}\n\n{res.text}")
        except: pass

def monitoring():
    while True:
        try:
            rsi, p = get_data('5m')
            if rsi and (rsi < 30 or rsi > 78):
                prompt = f"{SYS}\nBTC RSI {rsi:.1f}. Сигнал 20x."
                res = client.models.generate_content(model=MODEL, contents=prompt)
                bot.send_message(CHAT_ID, f"⚠️ **СИГНАЛ**\n{res.text}")
                time.sleep(600)
            time.sleep(30)
        except: time.sleep(20)

if __name__ == "__main__":
    threading.Thread(target=monitoring, daemon=True).start()
    print("Бот в строю. Чекаю команди...")
    while True:
        try:
            bot.polling(none_stop=True, interval=2, timeout=20)
        except Exception as e:
            print(f"Помилка: {e}")
            time.sleep(10)