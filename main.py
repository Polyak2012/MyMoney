import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters
)
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
from io import BytesIO

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Подключение к SQLite
conn = sqlite3.connect('finance.db', check_same_thread=False)
cursor = conn.cursor()

# Создаём таблицу (без комментариев в SQL)
cursor.execute('''
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    type TEXT CHECK(type IN ('income', 'expense')),
    category TEXT,
    amount REAL,
    date TEXT,
    comment TEXT
)
''')
conn.commit()

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await update.message.reply_text(
        f"Привет, {user.first_name}! Это бот для учёта финансов.\n"
        "Доступные команды:\n"
        "/add_income - добавить доход\n"
        "/add_expense - добавить расход\n"
        "/stats - статистика\n"
        "/export - экспорт данных"
    )

# Добавление дохода
async def add_income(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Введите сумму дохода:")
    context.user_data['awaiting_input'] = 'income_amount'

# Обработка ввода
async def handle_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    text = update.message.text

    if 'awaiting_input' in context.user_data:
        if context.user_data['awaiting_input'] == 'income_amount':
            try:
                amount = float(text)
                cursor.execute(
                    'INSERT INTO transactions (user_id, type, amount, date) VALUES (?, ?, ?, date("now"))',
                    (user_id, 'income', amount)
                )
                conn.commit()
                await update.message.reply_text(f"Доход +{amount} записан!")
                context.user_data.pop('awaiting_input')
            except ValueError:
                await update.message.reply_text("Ошибка! Введите число.")

# Статистика
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    df = pd.read_sql_query(f'SELECT * FROM transactions WHERE user_id = {user_id}', conn)
    
    if df.empty:
        await update.message.reply_text("Нет данных для анализа.")
        return
    
    # График расходов по категориям
    expenses = df[df['type'] == 'expense']
    if not expenses.empty:
        expenses_by_category = expenses.groupby('category')['amount'].sum()
        plt.figure()
        expenses_by_category.plot(kind='pie', autopct='%1.1f%%')
        plt.title("Расходы по категориям")
        
        buf = BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)
        await update.message.reply_photo(photo=buf)
        plt.close()
    
    # Общий баланс
    total_income = df[df['type'] == 'income']['amount'].sum()
    total_expense = df[df['type'] == 'expense']['amount'].sum()
    balance = total_income - total_expense
    
    await update.message.reply_text(
        f"📊 Статистика:\n"
        f"Доходы: {total_income:.2f}\n"
        f"Расходы: {total_expense:.2f}\n"
        f"Баланс: {balance:.2f}"
    )

# Экспорт данных
async def export_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    df = pd.read_sql_query(f'SELECT * FROM transactions WHERE user_id = {user_id}', conn)
    
    if df.empty:
        await update.message.reply_text("Нет данных для экспорта.")
        return
    
    csv_data = df.to_csv(index=False)
    await update.message.reply_document(
        document=BytesIO(csv_data.encode()),
        filename='transactions.csv'
    )

# Ошибки
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Exception while handling an update:", exc_info=context.error)

def main() -> None:
    TOKEN = "8170415699:AAExCAt4lmMe2AcXuG3GamZNubaV7wD64jg"  # Замените на свой токен!
    
    # Создаем Application
    application = Application.builder().token(TOKEN).build()

    # Обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("add_income", add_income))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CommandHandler("export", export_data))
    
    # Обработка текстовых сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_input))
    
    # Обработка ошибок
    application.add_error_handler(error_handler)

    # Запуск бота
    application.run_polling()

if __name__ == '__main__':
    main()