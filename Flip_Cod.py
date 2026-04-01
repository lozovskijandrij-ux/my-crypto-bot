import telebot
import ccxt
import time
import pandas as pd
import threading
import sys
from google import genai

# --- НАЛАШТУВАННЯ ---
TG_TOKEN = "8674374290:AAEVD3XEGb1sbifJTqF1MN3mP_g3htKmanQ" # Новий токен
GEMINI_KEY = "AIzaSyAXRR_0Zyhacaux6SiyTr6czGjFId3R8F0"
CHAT_ID = "682352228"

# Статистика (скидається при перезапуску сервера)
stats = {"signals_sent": 0, "start_time": time.time()}

try:
    client = genai.Client(api_key=GEMINI_KEY)
    MODEL = "gemini-2.0-flash" # Оновив до актуальної стабільної моделі
    SYS_PROMPT = "Ти про-трейдер. Пиши коротко, мова: Українська. Аналізуй BTC для плеча 20x."
except Exception as e:
    print(f"Критична помилка AI: {e}")
    sys.exit(1)

bot = telebot.TeleBot(TG_TOKEN, threaded=False)
ex = ccxt.binance({'enableRateLimit': True})

def get_data(tf='5m'):
    try:
        ohlcv = ex.fetch_ohlcv('BTC/USDT', timeframe=tf, limit=50)
        df = pd.DataFrame(ohlcv, columns=['t', 'o', 'h', 'l', 'c', 'v'])
        
        # Розрахунок RSI
        delta = df['c'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        
        rs = gain.iloc[-1] / loss.iloc[-1] if loss.iloc[-1] != 0 else 0
        rsi = 100 - (100 / (1 + rs))
        return rsi, df['c'].iloc[-1]
    except Exception as e:
        print(f"Помилка даних: {e}")
        return None, None

@bot.message_handler(commands=['start', 'help'])
def send_welcome(m):
    bot.reply_to(m, "Бот активний 24/7 на Railway.\nКоманди: /now, /stats")

@bot.message_handler(commands=['stats'])
def send_stats(m):
    uptime_sec = int(time.time() - stats["start_time"])
    hours = uptime_sec // 3600
    minutes = (uptime_sec % 3600) // 60
    msg = (f"📈 **Статистика роботи**:\n"
           f"• Сигналів надіслано: {stats['signals_sent']}\n"
           f"• Час роботи: {hours}г {minutes}хв\n"
           f"• Статус: Live на Railway")
    bot.reply_to(m, msg)

@bot.message_handler(commands=['analysis', 'now', 'trend'])
def handle_commands(m):
    rsi, price = get_data()
    if rsi and price:
        liq_long = price * 0.952
        liq_short = price * 1.048
        
        prompt = f"{SYS_PROMPT}\nЦіна BTC: {price}, RSI: {rsi:.1f}. Дай швидкий прогноз."
        
        try:
            res = client.models.generate_content(model=MODEL, contents=prompt)
            ai_text = res.text if res.text else "AI не зміг сформувати відповідь."
            response = (f"📊 **BTC**: {price:.1f}$\n"
                        f"📈 **RSI**: {rsi:.1f}\n"
                        f"💀 **Liq (20x)**: L:{liq_long:.0f} / S:{liq_short:.0f}\n\n"
                        f"🤖 **AI**: {ai_text}")
            bot.reply_to(m, response)
        except Exception as e:
            bot.reply_to(m, f"Помилка AI: {e}")
    else:
        bot.reply_to(m, "Не вдалося отримати дані з біржі.")

def monitoring():
    while True:
        try:
            rsi, price = get_data('5m')
            # Сигнали при екстремальних значеннях
            if rsi and (rsi < 28 or rsi > 72):
                prompt = f"{SYS_PROMPT}\nУВАГА! RSI на рівні {rsi:.1f}, Ціна {price}. Напиши дію (BUY/SELL)."
                res = client.models.generate_content(model=MODEL, contents=prompt)
                
                msg = f"🚨 **СИГНАЛ RSI**: {rsi:.1f}\n💰 **Ціна**: {price}\n\n{res.text}"
                bot.send_message(CHAT_ID, msg)
                
                stats["signals_sent"] += 1
                time.sleep(600) # Пауза 10 хв після сигналу
            time.sleep(30)
        except Exception as e:
            print(f"Помилка моніторингу: {e}")
            time.sleep(20)

if __name__ == "__main__":
    # Запуск моніторингу в окремому потоці
    threading.Thread(target=monitoring, daemon=True).start()
    print("Бот в строю. Railway активний.")
    
    while True:
        try:
            bot.polling(none_stop=True, interval=1, timeout=30)
        except Exception as e:
            print(f"Помилка поллінгу: {e}")
            time.sleep(5)
