import logging
from random import choice

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from config import (CHATGPT_TOKEN, LANGUAGES)
from gpt import ChatGPTService
from utils import (send_image, send_text, load_message, show_main_menu, load_prompt, send_text_buttons)



chatgpt_service = ChatGPTService(CHATGPT_TOKEN)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_image(update, context, "start")
    await send_text(update, context, load_message("start"))
    await show_main_menu(
        update,
        context,
        {
            'start': 'Головне меню',
            'random': 'Дізнатися випадковий факт',
            'gpt': 'Запитати ChatGPT',
            'talk': 'Діалог з відомою особистістю',
            'translate': 'Перекладач текстів',
            'recommend': 'Рекомендації від GPT',
        }
    )


async def random(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_image(update, context, "random")
    message_to_delete = await send_text(update, context, "Шукаю випадковий факт ...")
    try:
        prompt = load_prompt("random")
        fact = await chatgpt_service.send_question(
            prompt_text=prompt,
            message_text="Розкажи про випадковий факт"
        )
        buttons = {
            'random': 'Хочу ще один факт',
            'start': 'Закінчити'
        }
        await send_text_buttons(update, context, fact, buttons)
    except Exception as e:
        logger.error(f"Помилка в обробнику /random: {e}")
        await send_text(update, context, "Помилка при отриманні випадкового факту.")
    finally:
        await context.bot.delete_message(
            chat_id=update.effective_chat.id,
            message_id=message_to_delete.message_id
        )


async def random_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data
    if data == 'random':
        await random(update, context)
    elif data == 'start':
        await start(update, context)


async def gpt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await send_image(update, context, "gpt")
    chatgpt_service.set_prompt(load_prompt("gpt"))
    await send_text(update, context, "Задайте питання ...")
    context.user_data["conversation_state"] = "gpt"


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message_text = update.message.text
    conversation_state = context.user_data.get("conversation_state")

    if conversation_state == "translate":
        target_lang = context.user_data.get("target_language")
        if not target_lang:
            await send_text(update, context, "Спочатку оберіть мову для перекладу!")
            return

        waiting_message = await send_text(update, context, "⏳ Перекладаю...")

        try:

            prompt = f"You are a professional translator. Translate the following text to {LANGUAGES[target_lang]}. Provide only the translation without any additional comments."


            response = await chatgpt_service.send_question(
                prompt_text=prompt,
                message_text=message_text
            )

            keyboard = []
            other_langs = [lang for lang in LANGUAGES.keys() if lang != target_lang]
            for i in range(0, len(other_langs), 2):
                row = []
                for code in other_langs[i:i + 2]:
                    row.append(
                        InlineKeyboardButton(
                            LANGUAGES[code],
                            callback_data=f"change_{code}"
                        )
                    )
                keyboard.append(row)

            keyboard.append([
                InlineKeyboardButton("❌ Закінчити", callback_data="finish_translate")
            ])

            reply_markup = InlineKeyboardMarkup(keyboard)

            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"📝 *Переклад ({LANGUAGES[target_lang]}):*\n\n{response}\n\n"
                         f"━━━━━━━━━━━━━━━\nНадішліть інший текст або оберіть дію:",
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )

        except Exception as e:
            logger.error(f"Помилка при перекладі: {e}")
            await send_text(update, context, "❌ Помилка при перекладі. Спробуйте ще раз.")
        finally:
            await context.bot.delete_message(
                chat_id=update.effective_chat.id,
                message_id=waiting_message.message_id
            )
        return

    if conversation_state == "recommend_genre":
        genre = message_text.strip()
        category = context.user_data.get("rec_category")

        if not category:
            await send_text(update, context, "Помилка: категорія не обрана. Використайте /recommend")
            return

        context.user_data["rec_genre"] = genre
        context.user_data["rec_disliked"] = []

        waiting_message = await send_text(update, context, "⏳ Шукаю найкращі рекомендації...")

        try:
            base_prompt = load_prompt("recommend")

            prompt = f"""{base_prompt}

        Порекомендуй одну річ у категорії "{category}" в жанрі "{genre}". 
        Дай ОДНУ конкретну рекомендацію з коротким описом (2-3 речення).

        Формат відповіді:
        📌 Назва
        Короткий опис чому це круто."""

            response = await chatgpt_service.send_question(
                prompt_text=prompt,
                message_text=""
            )
            lines = response.split('\n')
            recommendation_name = lines[0].replace('📌', '').strip() if lines else "Unknown"
            context.user_data["rec_disliked"] = [recommendation_name]

            buttons = {
                'rec_dislike': '👎 Не подобається',
                'start': '❌ Закінчити'
            }

            await send_text_buttons(
                update,
                context,
                f"🎯 *Рекомендація ({category}):*\n\n{response}",
                buttons
            )

        except Exception as e:
            logger.error(f"Помилка при отриманні рекомендації: {e}")
            await send_text(update, context, "❌ Виникла помилка при отриманні рекомендації.")

        finally:
            await context.bot.delete_message(
            chat_id=update.effective_chat.id,
            message_id=waiting_message.message_id
            )
        return


    if conversation_state == "gpt":
        waiting_message = await send_text(update, context, "...")
        try:
            response = await chatgpt_service.add_message(message_text)
            await send_text(update, context, response)
        except Exception as e:
            logger.error(f"Помилка при отриманні відповіді від ChatGPT: {e}")
            await send_text(update, context, "Виникла помилка при обробці вашого повідомлення.")
        finally:
            await context.bot.delete_message(
                chat_id=update.effective_chat.id,
                message_id=waiting_message.message_id
            )
    if conversation_state == "talk":
        personality = context.user_data.get("selected_personality")
        if personality:
            prompt = load_prompt(personality)
            chatgpt_service.set_prompt(prompt)
        else:
            await send_text(update, context, "Спочатку оберіть особистість для розмови!")
            return
        waiting_message = await send_text(update, context, "...")
        try:
            response = await chatgpt_service.add_message(message_text)
            buttons = {"start": "Закінчити"}
            personality_name = personality.replace("talk_", "").replace("_", " ").title()
            await send_text_buttons(update, context, f"{personality_name}: {response}", buttons)
        except Exception as e:
            logger.error(f"Помилка при отриманні відповіді від ChatGPT: {e}")
            await send_text(update, context, "Виникла помилка при отриманні відповіді!")
            await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=waiting_message.message_id)
        finally:
            await context.bot.delete_message(
                chat_id=update.effective_chat.id,
                message_id=waiting_message.message_id
            )
    if not conversation_state:
        intent_recognized = await inter_random_input(update, context, message_text)
        if not intent_recognized:
            await show_funny_response(update, context)
        return


async def talk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await send_image(update, context, "talk")
    personalities = {
        'talk_linus_torvalds': "Linus Torvalds (Linux, Git)",
        'talk_guido_van_rossum': "Guido van Rossum (Python)",
        'talk_mark_zuckerberg': "Mark Zuckerberg (Meta, Facebook)",
        'start': "Закінчити",
    }
    await send_text_buttons(update, context, "Оберіть особистість для спілкування ...", personalities)


async def talk_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data == "start":
        context.user_data.pop("conversation_state", None)
        context.user_data.pop("selected_personality", None)
        await start(update, context)
        return
    if data.startswith("talk_"):
        context.user_data.clear()
        context.user_data["selected_personality"] = data
        context.user_data["conversation_state"] = "talk"
        prompt = load_prompt(data)
        chatgpt_service.set_prompt(prompt)
        personality_name = data.replace("talk_", "").replace("_", " ").title()
        await send_image(update, context, data)
        buttons = {'start': "Закінчити"}
        await send_text_buttons(
            update,
            context,
            f"Hello, I`m {personality_name}."
            f"\nI heard you wanted to ask me something. "
            f"\nYou can ask questions in your native language.",
            buttons
        )


async def inter_random_input(update: Update, context: ContextTypes.DEFAULT_TYPE, message_text):
    message_text_lower = message_text.lower()
    if any(keyword in message_text_lower for keyword in ['факт', 'цікав', 'random', 'випадков']):
        await send_text(
            update,
            context,
            text="Схоже, ви цікавитесь випадковими фактами! Зараз покажу вам один..."
        )
        await random(update, context)
        return True

    elif any(keyword in message_text_lower for keyword in ['gpt', 'чат', 'питання', 'запита', 'дізнатися']):
        await send_text(
            update,
            context,
            text="Схоже, у вас є питання! Переходимо до режиму спілкування з ChatGPT..."
        )
        await gpt(update, context)
        return True

    elif any(keyword in message_text_lower for keyword in ['розмов', 'говори', 'спілкува', 'особист', 'talk']):
        await send_text(
            update,
            context,
            text="Схоже, ви хочете поговорити з відомою особистістю! Зараз покажу вам доступні варіанти..."
        )
        await talk(update, context)
        return True
    return False


async def show_funny_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    funny_responses = [
        "Хмм... Цікаво, але я не зрозумів, що саме ви хочете. Може спробуєте одну з команд з меню?",
        "Дуже цікаве повідомлення! Але мені потрібні чіткіші інструкції. Ось доступні команди:",
        "Ой, здається, ви мене застали зненацька! Я вмію багато чого, але мені потрібна конкретна команда:",
        "Вибачте, мої алгоритми не розпізнали це як команду. Ось що я точно вмію:",
        "Це повідомлення таке ж загадкове, як єдиноріг у дикій природі! Спробуйте одну з цих команд:",
        "Я намагаюся зрозуміти ваше повідомлення... Але краще скористайтесь однією з команд:",
        "О! Випадкове повідомлення! Я теж вмію бути випадковим, але краще використовуйте команди:",
        "Гм, не спрацювало. Може спробуємо ці команди?",
        "Це повідомлення прекрасне, як веселка! Але для повноцінного спілкування спробуйте:",
        "Згідно з моїми розрахунками, це повідомлення не відповідає жодній з моїх команд. Ось вони:",
    ]
    random_response = choice(funny_responses)
    available_commands = """
    - Не знаєте, що обрати? Почніть з /start,
    - Спробуйте команду /gpt, щоб задати питання,
    """
    full_message = f"{random_response}\n{available_commands}"
    await update.message.reply_text(full_message)


async def translate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from config import LANGUAGES

    context.user_data.clear()
    await send_image(update, context, "start")

    keyboard = []
    for i in range(0, len(LANGUAGES), 2):
        row = []
        items = list(LANGUAGES.items())[i:i + 2]
        for code, name in items:
            row.append(InlineKeyboardButton(name, callback_data=f"lang_{code}"))
        keyboard.append(row)

    reply_markup = InlineKeyboardMarkup(keyboard)

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="🌍 *Режим перекладача*\n\nОберіть мову, на яку хочете перекладати тексти:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )


async def translate_language_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from config import LANGUAGES

    query = update.callback_query
    await query.answer()

    lang_code = query.data.replace("lang_", "")
    context.user_data["target_language"] = lang_code
    context.user_data["conversation_state"] = "translate"

    await query.edit_message_text(
        f"✅ Обрано мову: *{LANGUAGES[lang_code]}*\n\n"
        f"Тепер надішліть мені текст для перекладу.",
        parse_mode="Markdown"
    )


async def translate_change_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from config import LANGUAGES

    query = update.callback_query
    await query.answer()

    if query.data == "finish_translate":
        context.user_data.pop("target_language", None)
        context.user_data.pop("conversation_state", None)
        await query.edit_message_text(
            "✅ Режим перекладу завершено.\n\n"
            "Використовуйте /translate, щоб почати знову."
        )
    else:
        lang_code = query.data.replace("change_", "")
        context.user_data["target_language"] = lang_code
        await query.edit_message_text(
            f"✅ Мову змінено на: *{LANGUAGES[lang_code]}*\n\n"
            f"Надішліть текст для перекладу.",
            parse_mode="Markdown"
        )


async def recommend(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await send_image(update, context, "start")

    categories = {
        'rec_movies': '🎬 Фільми',
        'rec_books': '📚 Книги',
        'rec_music': '🎵 Музика',
        'start': '❌ Закінчити'
    }

    await send_text_buttons(
        update,
        context,
        "🎯 *Рекомендації від GPT*\n\nОберіть категорію для отримання рекомендацій:",
        categories
    )


async def recommend_category_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data

    if data == "start":
        await start(update, context)
        return

    category_map = {
        'rec_movies': 'фільми',
        'rec_books': 'книги',
        'rec_music': 'музику'
    }

    context.user_data["rec_category"] = category_map.get(data)
    context.user_data["conversation_state"] = "recommend_genre"

    category_emoji = {
        'rec_movies': '🎬',
        'rec_books': '📚',
        'rec_music': '🎵'
    }

    await query.edit_message_text(
        f"{category_emoji.get(data)} Ви обрали: *{category_map.get(data)}*\n\n"
        f"Тепер введіть жанр, який вас цікавить.\n"
        f"Наприклад: _комедія, фантастика, детектив, рок, джаз..._",
        parse_mode="Markdown"
    )


async def recommend_dislike(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Шукаю інший варіант...")

    category = context.user_data.get("rec_category")
    genre = context.user_data.get("rec_genre")
    disliked = context.user_data.get("rec_disliked", [])

    if not category or not genre:
        await query.edit_message_text("Помилка: дані втрачено. Використайте /recommend для початку.")
        return

    await query.edit_message_text("⏳ Шукаю нові рекомендації...")

    try:
        base_prompt = load_prompt("recommend")

        disliked_text = ""
        if disliked:
            disliked_text = f"\n\nНЕ рекомендуй ці варіанти (вони вже не сподобались): {', '.join(disliked)}"


        prompt = f"""{base_prompt}

Порекомендуй одну річ у категорії "{category}" в жанрі "{genre}". 
Дай ОДНУ конкретну рекомендацію з коротким описом (2-3 речення).{disliked_text}

Формат відповіді:
📌 Назва
Короткий опис чому це круто."""

        response = await chatgpt_service.send_question(
            prompt_text=prompt,
            message_text=""
            )

        lines = response.split('\n')
        recommendation_name = lines[0].replace('📌', '').strip() if lines else "Unknown"

        disliked.append(recommendation_name)
        context.user_data["rec_disliked"] = disliked

        await query.edit_message_text(
            f"🎯 *Рекомендація ({category}):*\n\n{response}",
            parse_mode="Markdown"
        )
        buttons = {
            'rec_dislike': '👎 Не подобається',
            'start': '❌ Закінчити'
            }

        keyboard = []
        for key, value in buttons.items():
            button = InlineKeyboardButton(str(value), callback_data=str(key))
            keyboard.append([button])
        reply_markup = InlineKeyboardMarkup(keyboard)

        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="Оберіть дію:",
            reply_markup=reply_markup
        )

    except Exception as e:
        logger.error(f"Помилка при генерації рекомендації: {e}")
        await query.edit_message_text(
             "❌ Виникла помилка при генерації рекомендації. Спробуйте ще раз."
        )