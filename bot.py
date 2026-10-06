import os
import sqlite3
import logging
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- ИНИЦИАЛИЗА БАЗЫ ДАННЫХ ---
def init_db():
    conn = sqlite3.connect('salary.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS shifts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            date TEXT,
            revenue REAL,
            salary REAL
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# --- ФУНКЦИЯ РАСЧЕТА СТАВКИ ---
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

# --- КОМАНДА /start ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "👋 **Привет! Я бот для учета смен и зарплаты.**\n\n"
        "🔹 **Как записать смену:**\n"
        "• Просто отправь выручку за сегодня: `45000`\n"
        "• Или укажи дату и сумму: `05.10 52000`\n\n"
        "Используй кнопки ниже для просмотра статистики за месяц!"
    )
    await update.message.reply_markdown(msg, reply_markup=get_keyboard())

# --- ПОЛУЧЕНИЕ СТАТИСТИКИ ЗА МЕСЯЦ ---
def get_month_stats(user_id: int, month_str: str = None):
    if not month_str:
        month_str = datetime.now().strftime("%Y-%m")
        
    conn = sqlite3.connect('salary.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT COUNT(*), SUM(revenue), SUM(salary) 
        FROM shifts 
        WHERE user_id = ? AND date LIKE ?
    ''', (user_id, f"{month_str}%"))
    
    count, total_revenue, total_salary = cursor.fetchone()
    conn.close()
    
    return count or 0, total_revenue or 0.0, total_salary or 0.0

# --- ОБРАБОТКА ТЕКСТОВЫХ СООБЩЕНИЙ ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    raw_text = update.message.text.strip()
    
    # Режим просмотра статистики
    if raw_text == "📊 Статистика за месяц":
        count, total_rev, total_sal = get_month_stats(user_id)
        current_month = datetime.now().strftime("%m.%Y")
        
        msg = (
            f"📅 *Статистика за {current_month}*\n\n"
            f"🚩 Всего смен: *{count}*\n"
            f"💰 Общая выручка: *{total_rev:,.0f} грн*\n"
            f"💵 *Итого заработано: {total_sal:,.0f} грн*"
        ).replace(',', ' ')
        
        await update.message.reply_markdown(msg, reply_markup=get_keyboard())
        return

    # Режим просмотра истории
    if raw_text == "📜 История смен":
        conn = sqlite3.connect('salary.db')
        cursor = conn.cursor()
        current_month = datetime.now().strftime("%Y-%m")
        cursor.execute('''
            SELECT date, revenue, salary 
            FROM shifts 
            WHERE user_id = ? AND date LIKE ?
            ORDER BY date DESC LIMIT 10
        ''', (user_id, f"{current_month}%"))
        rows = cursor.fetchall()
        conn.close()
        
        if not rows:
            await update.message.reply_text("📭 В этом месяце пока нет записанных смен.")
            return
            
        history_msg = "📜 *Последние смены этого месяца:*\n\n"
        for date_str, rev, sal in rows:
            history_msg += f"🗓 `{date_str}`: Выручка *{rev:,.0f} грн* ➔ Зарплата: *{sal:,.0f} грн*\n".replace(',', ' ')
            
        await update.message.reply_markdown(history_msg, reply_markup=get_keyboard())
        return

    # Парсинг ввода смены (дата + сумма или просто сумма)
    parts = raw_text.split()
    date_str = datetime.now().strftime("%Y-%m-%d")
    revenue_str = ""

    if len(parts) == 1:
        revenue_str = parts[0]
    elif len(parts) == 2:
        # Введена дата и сумма (например: 05.10 45000)
        date_input = parts[0]
        revenue_str = parts[1]
        try:
            day, month = date_input.split('.')
            year = datetime.now().year
            date_str = f"{year}-{int(month):02d}-{int(day):02d}"
        except Exception:
            await update.message.reply_text("⚠️ Неверный формат даты. Используйте формат `ДД.ММ Сумма`, например: `05.10 45000`")
            return

    # Очищаем сумму
    clean_revenue = "".join([c for c in revenue_str if c.isdigit() or c in ['.', ',']]).replace(',', '.')
    
    try:
        revenue = float(clean_revenue)
        if revenue < 0:
            await update.message.reply_text("⚠️ Сумма должна быть положительной.")
            return
            
        salary = calculate_salary(revenue)
        
        # Сохраняем смену в базу данных
        conn = sqlite3.connect('salary.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO shifts (user_id, date, revenue, salary)
            VALUES (?, ?, ?, ?)
        ''', (user_id, date_str, revenue, salary))
        conn.commit()
        conn.close()
        
        # Получаем обновленную статистику за месяц
        count, _, total_sal = get_month_stats(user_id, date_str[:7])
        
        msg = (
            f"✅ *Смена записана!* ({date_str})\n\n"
            f"💰 Выручка за день: *{revenue:,.0f} грн*\n"
            f"💵 Зарплата за день: *{salary:,.0f} грн*\n\n"
            f"📈 Всего за месяц ({count} смен): *{total_sal:,.0f} грн*"
        ).replace(',', ' ')
        
        await update.message.reply_markdown(msg, reply_markup=get_keyboard())
        
    except ValueError:
        await update.message.reply_text("⚠️ Не удалось распознать сумму. Введите число (например `45000` или `05.10 45000`).")

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).
