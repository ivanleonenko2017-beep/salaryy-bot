import os
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Привет! Введи сумму дневной выручки (числом), и я рассчитаю зарплату.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.replace(" ", "").replace(",", ".")
    try:
        revenue = float(text)
        if revenue < 0:
            await update.message.reply_text("⚠️ Введите положительное число.")
            return
        
        salary = calculate_salary(revenue)
        msg = (
            f"📊 *Расчет зарплаты за день*\n\n"
            f"💰 Выручка: *{revenue:,.0f} грн*\n"
            f"💵 Зарплата: *{salary:,.0f} грн*"
        )
        await update.message.reply_markdown(msg)
    except ValueError:
        await update.message.reply_text("⚠️ Введите корректное число (сумму выручки).")

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()
