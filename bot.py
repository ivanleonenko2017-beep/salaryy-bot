import os
import json
import logging
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
DATA_FILE = "data.json"

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- РАБОТА С ХРАНИЛИЩЕМ (JSON) ---
def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"Ошибка чтения файла: {e}")
    return {}

def save_data(data):
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"Ошибка сохранения файла: {e}")

# --- ШКАЛА СТАВОК (СЕТКА) ---
def calculate_salary(revenue: float) -> int:
    if revenue < 40000:
        return 1300
    elif 40000 <= revenue < 50000:
        return 1500
    elif 50000 <= revenue < 60000:
        return 1700
    elif 60000 <= revenue < 70000:
        return 1900
    elif 70000 <= revenue < 80000:
        return 2000
    elif 80000 <= revenue < 90000:
        return 2100
    else:
        return 2200

# --- КЛАВИАТУРА ---
def get_keyboard():
    return ReplyKeyboardMarkup(
        [["📊 Статистика за месяц", "📜 История смен"]],
        resize_keyboard=True
    )

# --- /START ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "👋 **Бот учета зарплаты и смен**\n\n"
        "🔹 **Как вводить данные:**\n"
        "• Отправить сумму за сегодня: `45000`\n"
        "• Отправить дату и сумму: `05.10 52000`\n\n"
        "Используй кнопки ниже для просмотра итогов за месяц!"
    )
    await update.message.reply_markdown(msg, reply_markup=get_keyboard())

# --- ОБРАБОТКА СООБЩЕНИЙ ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    text = update.message.text.strip()
    data = load_data()

    if user_id not in data:
        data[user_id] = []

    # 📊 СТАТИСТИКА ЗА МЕСЯЦ
    if text == "📊 Статистика за месяц":
        current_month = datetime.now().strftime("%m.%Y")
        user_shifts = data.get(user_id, [])
        
        month_shifts = [s for s in user_shifts if datetime.strptime(s["date"], "%Y-%m-%d").strftime("%m.%Y") == current_month]
        
        if not month_shifts:
            await update.message.reply_markdown(f"📭 В этом месяце ({current_month}) смен еще нет.", reply_markup=get_keyboard())
            return

        total_rev = sum(s["revenue"] for s in month_shifts)
        total_sal = sum(s["salary"] for s in month_shifts)
        count = len(month_shifts)

        msg = (
            f"📅 *Статистика за {current_month}*\n\n"
            f"🚩 Всего смен: *{count}*\n"
            f"💰 Общая выручка/заказы: *{total_rev:,.0f} грн*\n"
            f"💵 *Итого заработано: {total_sal:,.0f} грн*"
        ).replace(',', ' ')
        
        await update.message.reply_markdown(msg, reply_markup=get_keyboard())
        return

    # 📜 ИСТОРИЯ СМЕН
    if text == "📜 История смен":
        user_shifts = data.get(user_id, [])
        if not user_shifts:
            await update.message.reply_text("📭 История смен пуста.", reply_markup=get_keyboard())
            return

        recent_shifts = sorted(user_shifts, key=lambda x: x["date"], reverse=True)[:10]
        msg = "📜 *Последние записанные смены:*\n\n"
        
        for s in recent_shifts:
            d = datetime.strptime(s["date"], "%Y-%m-%d").strftime("%d.%m.%Y")
            msg += f"🗓 `{d}`: Заказы *{s['revenue']:,.0f} грн* ➔ Зарплата: *{s['salary']:,.0f} грн*\n".replace(',', ' ')

        await update.message.reply_markdown(msg, reply_markup=get_keyboard())
        return

    # ВВОД СУММЫ / ДАТЫ
    parts = text.split()
    date_str = datetime.now().strftime("%Y-%m-%d")
    rev_raw = ""

    if len(parts) == 1:
        rev_raw = parts[0]
    elif len(parts) == 2:
        date_input, rev_raw = parts[0], parts[1]
        try:
            day, month = date_input.split('.')
            year = datetime.now().year
            date_str = f"{year}-{int(month):02d}-{int(day):02d}"
        except Exception:
            await update.message.reply_text("⚠️ Ошибка даты! Вводи в формате `ДД.ММ Сумма` (например: `05.10 45000`).")
            return

    clean_rev = "".join([c for c in rev_raw if c.isdigit() or c in ['.', ',']]).replace(',', '.')
    
    try:
        revenue = float(clean_rev)
        if revenue < 0:
            await update.message.reply_text("⚠️ Сумма должна быть больше нуля.")
            return

        salary = calculate_salary(revenue)

        # Сохраняем или обновляем смену на эту дату
        user_shifts = data[user_id]
        updated = False
        for s in user_shifts:
            if s["date"] == date_str:
                s["revenue"] = revenue
                s["salary"] = salary
                updated = True
                break

        if not updated:
            user_shifts.append({"date": date_str, "revenue": revenue, "salary": salary})

        save_data(data)

        d_formatted = datetime.strptime(date_str, "%Y-%m-%d").strftime("%d.%m.%Y")
        
        # Считаем актуальный месяц
        current_m = datetime.strptime(date_str, "%Y-%m-%d").strftime("%m.%Y")
        m_shifts = [s for s in user_shifts if datetime.strptime(s["date"], "%Y-%m-%d").strftime("%m.%Y") == current_m]
        total_m_sal = sum(s["salary"] for s in m_shifts)

        msg = (
            f"✅ *Смена за {d_formatted} записана!*\n\n"
            f"💰 Выручка/Заказы: *{revenue:,.0f} грн*\n"
            f"💵 Зарплата за день: *{salary:,.0f} грн*\n\n"
            f"📈 Заработано за месяц ({len(m_shifts)} смен): *{total_m_sal:,.0f} грн*"
        ).replace(',', ' ')

        await update.message.reply_markdown(msg, reply_markup=get_keyboard())

    except ValueError:
        await update.message.reply_text("⚠️ Не понял сумму. Введи просто число (например `45000`) или `05.10 45000`.")

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()
