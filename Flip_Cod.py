import telebot
import ccxt
import time
import pandas as pd
import threading
import sys
from google import genai

# --- НАЛАШТУВАННЯ ---
TG_TOKEN = "8674374290:AAEVD3XEGb1sbifJTqF1MN3mP_g3htKmanQ"
GEMINI_KEY = "AIzaSyAXRR_0Zyhacaux6SiyTr6czGjFId3R8F0"
CHAT_ID = "682352228"

stats = {"signals_sent": 0, "start_time": time.time()}

try:
    client = genai.Client(api_key=GEMINI_KEY)
    MODEL = "gemini-2.0-flash"
    SYS_PROMPT = "Ти про-трейдер. Пиши коротко, мова: Українська. Аналізуй BTC для плеча 20x."
except Exception as e:
    print(f"Помилка AI: {e}")
    sys.exit(1)

# ПРАВИЛЬНИЙ BYBIT
ex = ccxt.bybit({'enableRateLimit': True})
bot = telebot.TeleBot(TG_TOKEN, threaded=False)

def get_data(tf='5m'):
    try:
        ohlcv = ex.fetch_ohlcv('BTC/USDT', timeframe=tf, limit=50)
        df = pd.DataFrame(ohlcv, columns=['t', 'o', 'h', 'l', 'c', 'v'])
        
        delta = df['c'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        
        rs = gain.iloc[-1] / loss.iloc[-1] if loss.iloc[-1] != 0 else 0
        rsi = 100 - (100 / (1 + rs))
        return rsi, df['c'].iloc[-1]
    except Exception as e:
        print(f"Помилка Bybit: {e}")
        return None, None

@bot.message_handler(commands=['start'])
def send_welcome(m):
    bot.reply_to(m, "Бот на Bybit активний. Команди: /now, /stats")

@bot.message_handler(commands=['stats'])
def send_stats(m):
    uptime_sec = int(time.time() - stats["start_time"])
    hours = uptime_sec // 3600
    minutes = (uptime_sec % 3600) // 60
    msg = (f"📈 **Bybit Статистика**:\n"
           f"• Сигналів: {stats['signals_sent']}\n"
           f"• Час роботи: {hours}г {minutes}хв")
    bot.reply_to(m, msg)

@bot.message_handler(commands=['now', 'analysis'])
def handle_commands(m):
    rsi, price = get_data()
    if rsi and price:
        liq_l, liq_s = price * 0.952, price * 1.048
        prompt = f"{SYS_PROMPT}\nBTC: {price}, RSI: {rsi:.1f}. Що робити?"
        try:
            res = client.models.generate_content(model=MODEL, contents=prompt)
            bot.reply_to(m, f"📊 **BTC (Bybit)**: {price:.1f}$\n📈 **RSI**: {rsi:.1f}\n💀 **Liq**: {liq_l:.0f}/{liq_s:.0f}\n\n🤖: {res.text}")
        except:
            bot.reply_to(m, f"📊 BTC: {price}, RSI: {rsi:.1f}. AI тимчасово спить.")
    else:
        bot.reply_to(m, "Біржа не відповідає. Перевір логи Railway.")

def monitoring():
    while True:
        try:
            rsi, price = get_data('5m')
            if rsi and (rsi < 29 or rsi > 71):
                prompt = f"{SYS_PROMPT}\nBTC RSI {rsi:.1f}, Ціна {price}. Дай сигнал!"
                res = client.models.generate_content(model=MODEL, contents=prompt)
                bot.send_message(CHAT_ID, f"🚨 **СИГНАЛ**: {rsi:.1f}\n{res.text}")
                stats["signals_sent"] += 1
                time.sleep(600)
            time.sleep(30)
        except:
            time.sleep(20)

if __name__ == "__main__":
    threading.Thread(target=monitoring, daemon=True).start()
    print("Бот в строю. Railway активний.")
    while True:
        try:
            bot.polling(none_stop=True, interval=1, timeout=40)
        except Exception as e:
            print(f"Помилка: {e}")
            time.sleep(5)
