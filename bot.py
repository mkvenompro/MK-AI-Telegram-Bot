import logging
import re

from telegram import Update
from telegram.constants import ChatType
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from config import TELEGRAM_BOT_TOKEN, MAX_HISTORY
from ai import ask_ai
from memory import get_history, add_message, clear_history

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)
BOT_USERNAME = None

def clean_question(text):
    global BOT_USERNAME
    text = text.strip()

    if BOT_USERNAME:
        text = re.sub(
            rf"@{re.escape(BOT_USERNAME)}",
            "",
            text,
            flags=re.IGNORECASE,
        )

    return text.strip()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 أهلاً بيك!\n\n"
        "أنا MK AI.\n\n"
        "في الجروب اعمل Mention ليا واسألني:\n"
        "@YourBot سؤالك هنا\n\n"
        "الأوامر:\n"
        "/help - المساعدة\n"
        "/reset - مسح المحادثة"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 MK AI\n\n"
        "في الجروب:\n"
        "@YourBot سؤالك\n\n"
        "/start\n"
        "/help\n"
        "/reset"
    )

async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    clear_history(chat_id)
    await update.message.reply_text("🧹 تم مسح Memory الخاصة بالمحادثة.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global BOT_USERNAME

    message = update.effective_message

    if not message or not message.text:
        return

    if message.from_user and message.from_user.is_bot:
        return

    text = message.text.strip()

    if BOT_USERNAME is None:
        me = await context.bot.get_me()
        BOT_USERNAME = me.username

    chat_type = update.effective_chat.type

    if chat_type in (ChatType.GROUP, ChatType.SUPERGROUP):
        mention = f'@{BOT_USERNAME.lower()}'

        if mention not in text.lower():
            return

        question = clean_question(text)
    else:
        question = text

    if not question:
        await message.reply_text("اكتب سؤالك بعد الـ Mention 😄")
        return

    chat_id = update.effective_chat.id
    history = get_history(chat_id, MAX_HISTORY)

    add_message(chat_id, 'user', question, MAX_HISTORY)

    await context.bot.send_chat_action(
        chat_id=chat_id,
        action='typing',
    )

    try:
        history_for_ai = history + [
            {
                'role': 'user',
                'content': question,
            }
        ]

        answer = await ask_ai(history_for_ai)

    except Exception as error:
        logger.exception('AI error: %s', error)
        await message.reply_text("❌ حصل خطأ وأنا بحاول أتواصل مع الـ AI.\nجرب تاني بعد شوية.")
        return

    add_message(chat_id, 'assistant', answer, MAX_HISTORY)

    await message.reply_text(
        answer,
        reply_to_message_id=message.message_id,
    )

async def error_handler(update, context):
    logger.exception(
        'Unhandled exception:',
        exc_info=context.error,
    )

async def post_init(application):
    global BOT_USERNAME

    me = await application.bot.get_me()
    BOT_USERNAME = me.username

    await application.bot.set_my_commands([
        ('start', 'Start the bot'),
        ('help', 'Show help'),
        ('reset', 'Clear conversation memory'),
    ])

    logger.info('Bot started: @%s', BOT_USERNAME)

def main():
    application = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('help', help_command))
    application.add_handler(CommandHandler('reset', reset_command))

    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_message,
        )
    )

    application.add_error_handler(error_handler)

    logger.info('Starting Telegram polling...')

    application.run_polling()

if __name__ == '__main__':
    main()