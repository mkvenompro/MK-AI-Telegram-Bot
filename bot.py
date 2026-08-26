import logging
import os
import re

from telegram import Update
from telegram.constants import ChatType
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from config import (
    TELEGRAM_BOT_TOKEN,
    MAX_HISTORY,
    MAX_MESSAGE_LENGTH,
)

from ai import ask_ai
from memory import (
    get_history,
    add_message,
    clear_history,
)


# ==================================================
# LOGGING
# ==================================================

logging.basicConfig(
    format=(
        "%(asctime)s - "
        "%(name)s - "
        "%(levelname)s - "
        "%(message)s"
    ),
    level=logging.INFO,
)

logger = logging.getLogger(
    __name__
)

BOT_USERNAME = None


# ==================================================
# TEXT CLEANING
# ==================================================

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


# ==================================================
# START
# ==================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not update.message:
        return

    await update.message.reply_text(
        "🤖 أهلاً بيك!\n\n"
        "أنا MK AI Agent.\n\n"
        "أقدر أستخدم:\n"
        "🌐 Web Search\n"
        "🐙 GitHub\n"
        "📄 URL Fetch\n"
        "💻 Linux Terminal\n"
        "📁 File Reader\n"
        "🔧 Git\n"
        "📦 تثبيت أدوات Linux\n"
        "🧠 Memory\n"
        "🔄 Multi-step Agent\n\n"
        "في الجروب اعمل Mention ليا "
        "واسألني."
    )


# ==================================================
# HELP
# ==================================================

async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not update.message:
        return

    await update.message.reply_text(
        "🤖 MK AI Agent\n\n"
        "/start - تشغيل\n"
        "/help - المساعدة\n"
        "/reset - مسح Memory\n\n"
        "مثال:\n"
        "@YourBot ابحث في GitHub "
        "عن yfmarco dev\n\n"
        "أو:\n"
        "@YourBot افتح README بتاع الريبو ده"
    )


# ==================================================
# RESET
# ==================================================

async def reset_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not update.effective_chat:
        return

    clear_history(
        update.effective_chat.id
    )

    if update.message:

        await update.message.reply_text(
            "🧹 تم مسح Memory الخاصة بالمحادثة."
        )


# ==================================================
# MESSAGE
# ==================================================

async def handle_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    global BOT_USERNAME

    message = update.effective_message

    if not message:
        return

    if not message.text:
        return

    if (
        message.from_user
        and message.from_user.is_bot
    ):
        return

    text = message.text.strip()

    if not text:
        return

    # --------------------------------------------------
    # GET BOT USERNAME
    # --------------------------------------------------

    if BOT_USERNAME is None:

        try:

            me = await context.bot.get_me()

            BOT_USERNAME = me.username

        except Exception as e:

            logger.error(
                "get_me failed: %r",
                e,
            )

    # --------------------------------------------------
    # GROUP LOGIC
    # --------------------------------------------------

    chat_type = (
        update.effective_chat.type
        if update.effective_chat
        else None
    )

    if chat_type in (
        ChatType.GROUP,
        ChatType.SUPERGROUP,
    ):

        mentioned = False

        is_reply_to_bot = False

        # ----------------------------------------------
        # Telegram entities
        # ----------------------------------------------

        if message.entities:

            for entity in message.entities:

                if entity.type != "mention":
                    continue

                mention_text = text[
                    entity.offset:
                    entity.offset
                    + entity.length
                ]

                if (
                    BOT_USERNAME
                    and mention_text.lower()
                    == (
                        "@"
                        + BOT_USERNAME.lower()
                    )
                ):

                    mentioned = True

                    break

        # ----------------------------------------------
        # Fallback mention
        # ----------------------------------------------

        if (
            not mentioned
            and BOT_USERNAME
        ):

            mentioned = (
                f"@{BOT_USERNAME.lower()}"
                in text.lower()
            )

        # ----------------------------------------------
        # Reply to bot
        # ----------------------------------------------

        if message.reply_to_message:

            replied = (
                message.reply_to_message
            )

            if (
                replied.from_user
                and replied.from_user.id
                == context.bot.id
            ):

                is_reply_to_bot = True

        if (
            not mentioned
            and not is_reply_to_bot
        ):
            return

        question = clean_question(
            text
        )

        # ----------------------------------------------
        # Previous bot context
        # ----------------------------------------------

        if (
            is_reply_to_bot
            and message.reply_to_message
            and message.reply_to_message.text
        ):

            previous = (
                message
                .reply_to_message
                .text
                .strip()
            )

            if question:

                question = (
                    "السياق السابق من رد البوت:\n"
                    + previous
                    + "\n\n"
                    "رسالة المستخدم الحالية:\n"
                    + question
                )

            else:

                question = previous

    else:

        question = text

    # ==================================================
    # EMPTY
    # ==================================================

    if not question:

        await message.reply_text(
            "اكتب سؤالك بعد الـ Mention 😄"
        )

        return

    # ==================================================
    # LENGTH
    # ==================================================

    if len(question) > MAX_MESSAGE_LENGTH:

        question = question[
            :MAX_MESSAGE_LENGTH
        ]

    # ==================================================
    # MEMORY
    # ==================================================

    chat_id = (
        update.effective_chat.id
    )

    history = get_history(
        chat_id,
        MAX_HISTORY,
    )

    add_message(
        chat_id,
        "user",
        question,
        MAX_HISTORY,
    )

    # ==================================================
    # TYPING
    # ==================================================

    try:

        await context.bot.send_chat_action(
            chat_id=chat_id,
            action="typing",
        )

    except Exception:
        pass

    # ==================================================
    # AI AGENT
    # ==================================================

    try:

        logger.info(
            "Agent request: %s",
            question[:500],
        )

        answer = await ask_ai(
            question,
            history,
        )

    except Exception as error:

        logger.exception(
            "AI error: %r",
            error,
        )

        await message.reply_text(
            "❌ حصل خطأ وأنا بتواصل "
            "مع الـ AI Agent."
        )

        return

    # ==================================================
    # MEMORY
    # ==================================================

    add_message(
        chat_id,
        "assistant",
        answer,
        MAX_HISTORY,
    )

    # ==================================================
    # TELEGRAM LIMIT
    # ==================================================

    if len(answer) <= 4000:

        await message.reply_text(
            answer,
            reply_to_message_id=(
                message.message_id
            ),
        )

    else:

        # Telegram message limit.
        chunks = [
            answer[i:i + 3900]
            for i in range(
                0,
                len(answer),
                3900,
            )
        ]

        for chunk in chunks:

            await message.reply_text(
                chunk
            )


# ==================================================
# ERROR HANDLER
# ==================================================

async def error_handler(
    update,
    context,
):

    logger.exception(
        "Unhandled exception",
        exc_info=context.error,
    )


# ==================================================
# POST INIT
# ==================================================

async def post_init(
    application,
):

    global BOT_USERNAME

    me = await application.bot.get_me()

    BOT_USERNAME = me.username

    await application.bot.set_my_commands([
        (
            "start",
            "Start the bot",
        ),
        (
            "help",
            "Show help",
        ),
        (
            "reset",
            "Clear memory",
        ),
    ])

    logger.info(
        "Bot started: @%s",
        BOT_USERNAME,
    )


# ==================================================
# MAIN
# ==================================================

def main():

    from telegram.request import HTTPXRequest

    telegram_request = HTTPXRequest(
        connection_pool_size=8,
        connect_timeout=30,
        read_timeout=60,
        write_timeout=60,
        pool_timeout=30,
    )

    updates_request = HTTPXRequest(
        connection_pool_size=8,
        connect_timeout=30,
        read_timeout=90,
        write_timeout=60,
        pool_timeout=30,
    )

    application = (
        Application.builder()
        .token(
            TELEGRAM_BOT_TOKEN
        )
        .post_init(
            post_init
        )
        .request(
            telegram_request
        )
        .get_updates_request(
            updates_request
        )
        .build()
    )

    application.add_handler(
        CommandHandler(
            "start",
            start,
        )
    )

    application.add_handler(
        CommandHandler(
            "help",
            help_command,
        )
    )

    application.add_handler(
        CommandHandler(
            "reset",
            reset_command,
        )
    )

    application.add_handler(
        MessageHandler(
            filters.TEXT
            & ~filters.COMMAND,
            handle_message,
        )
    )

    application.add_error_handler(
        error_handler
    )

    logger.info(
        "Starting Telegram polling..."
    )

    application.run_polling(
        drop_pending_updates=True,
        poll_interval=1.0,
        close_loop=True,
    )


if __name__ == "__main__":
    main()
