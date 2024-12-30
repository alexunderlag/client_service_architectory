import logging
import telebot
from telebot import types
import pymysql
from datetime import datetime
from random import choice
import hashlib
import asyncio
import time

def delete_message(chat_id, message_id):
    try:
        bot.delete_message(chat_id, message_id)
    except telebot.apihelper.ApiTelegramException as e:
        if e.error_code == 400 and "message to delete not found" in e.description:
            logger.warning(f"Message {message_id} not found, it might have already been deleted.")
        else:
            logger.error(f"Error deleting message {message_id}: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"Error deleting message {message_id}: {e}", exc_info=True)

# Проверка, решал ли пользователь этот вопрос раньше
def has_user_answered_question(user_id, question_id):
    connection = create_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT COUNT(*) FROM passedquestions WHERE user_id = %s AND question_id = %s", (user_id, question_id))
    answered = cursor.fetchone()['COUNT(*)'] > 0
    cursor.close()
    connection.close()
    return answered

# Настройка логгирования
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    handlers=[logging.FileHandler("bot.log"),
                              logging.StreamHandler()])

logger = logging.getLogger(__name__)

# Инициализация бота
API_TOKEN = '6816488325:AAGHMJCz_rwCPMVJkX255M-diou5FIJg0D0'
bot = telebot.TeleBot(API_TOKEN)

telebot.logger.setLevel(logging.INFO)  # Настройка уровня логирования telebot

# Подключение к базе данных
def create_connection():
    try:
        return pymysql.connect(
            host="localhost",
            user="root",
            password="1357924680qQ",
            database="it_bot",
            cursorclass=pymysql.cursors.DictCursor
        )
    except Exception as e:
        logger.error(f"Error in create_connection: {e}", exc_info=True)
        return None

user_questions = {}
user_complaints = {}
user_messages = {}
MAX_MESSAGES_TO_DELETE = 100

# Обработчик команды /start
@bot.message_handler(commands=['start'])
def handle_start(message):
    try:
        user_id = message.from_user.id
        if not get_user_id(user_id):
            register_user(user_id)
        delete_all_messages(message.chat.id)
        send_message(message.chat.id, "<B>Айтишечка Квиз Бот</B>\nДобро пожаловать бот работает в тестовом режиме:", reply_markup=generate_inline_main_menu(), parse_mode="html")
    except Exception as e:
        logger.error(f"Error in handle_start: {e}", exc_info=True)
        send_message(message.chat.id, "Произошла ошибка. Пожалуйста, попробуйте снова.")


# Удаление сообщений
def delete_message(chat_id, message_id):
    try:
        bot.delete_message(chat_id, message_id)
    except Exception as e:
        logger.error(f"Error deleting message {message_id}: {e}", exc_info=True)

def delete_last_message(chat_id):
    if chat_id in user_messages and user_messages[chat_id]:
        last_message = user_messages[chat_id].pop()
        if isinstance(last_message, tuple) and len(last_message) == 2 and isinstance(last_message[1], int):
            message_id = last_message[1]
            delete_message(chat_id, message_id)
        else:
            logger.error(f"Message data format is incorrect or message_id is not an integer: {last_message}")

def delete_all_messages(chat_id):
    if chat_id in user_messages:
        messages_to_delete = [msg_id for msg_type, msg_id in user_messages[chat_id] if isinstance(msg_id, int)]
        for message_id in messages_to_delete:
            delete_message(chat_id, message_id)
        user_messages[chat_id] = []
# Удаление сообщений
@bot.callback_query_handler(func=lambda call: call.data.startswith('complaint_'))
def handle_complaint(call):
    try:
        question_id = call.data.split('_')[1]
        user_id = get_user_id(call.from_user.id)
        user_complaints[user_id] = question_id  # Сохраняем вопрос для пользователя
        send_message(call.message.chat.id, "Введите текст вашей жалобы:")
        bot.register_next_step_handler(call.message, handle_complaint_text)
    except Exception as e:
        logger.error(f"Error in handle_complaint: {e}", exc_info=True)
        send_message(call.message.chat.id, "Произошла ошибка. Пожалуйста, попробуйте снова.")

def handle_complaint_text(message):
    try:
        user_id = get_user_id(message.from_user.id)
        question_id = user_complaints.get(user_id)
        complaint_text = message.text
        if question_id and complaint_text:
            save_complaint(user_id, question_id, complaint_text)
            delete_last_message(message.chat.id)  # Удаляем сообщение "Введите текст вашей жалобы"
            delete_message(message.chat.id, message.message_id)  # Удаляем сообщение с текстом жалобы
            send_message(
                message.chat.id,
                "Ваша жалоба отправлена на рассмотрение.",
                reply_markup=generate_complaint_confirmation_markup()
            )
        else:
            send_message(message.chat.id, "Не удалось отправить жалобу. Попробуйте снова.")
    except Exception as e:
        logger.error(f"Error in handle_complaint_text: {e}", exc_info=True)
        send_message(message.chat.id, "Произошла ошибка. Пожалуйста, попробуйте снова.")

@bot.callback_query_handler(func=lambda call: call.data == 'back_to_questions')
def handle_back_to_questions(call):
    try:
        user_id = get_user_id(call.from_user.id)
        last_question_id = get_last_question_id(user_id)
        difficulty_id = get_question_difficulty(last_question_id)

        delete_all_messages(call.message.chat.id)  # Удаляем все сообщения перед отображением следующего вопроса

        send_next_question(call.message, user_id, difficulty_id)
    except Exception as e:
        logger.error(f"Error in handle_back_to_questions: {e}", exc_info=True)
        send_message(call.message.chat.id, "Произошла ошибка. Пожалуйста, попробуйте снова.")
def save_complaint(user_id, question_id, complaint_text):
    try:
        connection = create_connection()
        if connection:
            cursor = connection.cursor()
            cursor.execute("INSERT INTO complaints (user_id, question_id, complaint_text, complaint_date) VALUES (%s, %s, %s, %s)",
                           (user_id, question_id, complaint_text, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            connection.commit()
            cursor.close()
            connection.close()
    except Exception as e:
        logger.error(f"Error in save_complaint: {e}", exc_info=True)

# Регистрация пользователя
def register_user(telegram_id):
    try:
        connection = create_connection()
        if connection:
            cursor = connection.cursor()
            cursor.execute("INSERT INTO users (username, registration_date, rating, correct_answers_count, incorrect_answers_count, show_nickname, show_correct_answers) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                           (telegram_id, datetime.now().strftime('%Y-%m-%d'), 0, 0, 0, True, True))
            connection.commit()
            print(f"User registered: {telegram_id}")
            cursor.close()
            connection.close()
    except Exception as e:
        logger.error(f"Error in register_user: {e}", exc_info=True)

def get_user_id(telegram_id):
    try:
        connection = create_connection()
        if connection:
            cursor = connection.cursor()
            cursor.execute("SELECT user_id FROM users WHERE username = %s", (telegram_id,))
            result = cursor.fetchone()
            cursor.close()
            connection.close()
            if result:
                logger.info(f"User ID for telegram_id {telegram_id}: {result['user_id']}")
                return result['user_id']
        logger.info(f"No user found for telegram_id {telegram_id}")
        return None
    except Exception as e:
        logger.error(f"Error in get_user_id: {e}", exc_info=True)
        return None

# Обработчик главного меню
@bot.message_handler(func=lambda message: message.text in ['Категории', 'Профиль', 'Админка', 'Добавить вопрос', 'Донат'])
def handle_main_menu(message):
    try:
        if message.text == 'Категории':
            send_message(message.chat.id, "Выберите категорию:", reply_markup=generate_categories_markup())
        elif message.text == 'Профиль':
            show_profile_without_menu(message)
        elif message.text == 'Админка':
            send_message(message.chat.id, "Админка (функционал в разработке).", reply_markup=generate_inline_main_menu())
        elif message.text == 'Добавить вопрос':
            send_message(message.chat.id, "Напишите свой вопрос:")
            bot.register_next_step_handler(message, handle_question_input)
        elif message.text == 'Донат':
            send_message(message.chat.id, "Принимаем перевод на карту: 2202206264599551 (На оплату сервера, чая и печенек).")
    except Exception as e:
        logger.error(f"Error in handle_main_menu: {e}", exc_info=True)
        send_message(message.chat.id, "Произошла ошибка. Пожалуйста, попробуйте снова.")

# Генерация меню категорий
def generate_categories_markup():
    try:
        markup = types.InlineKeyboardMarkup(row_width=2)
        connection = create_connection()
        if connection:
            cursor = connection.cursor()
            cursor.execute("SELECT category_name FROM categories")
            categories = cursor.fetchall()
            buttons = []
            for category in categories:
                category_name = category['category_name']
                callback_data = f'category_{hashlib.md5(category_name.encode()).hexdigest()}'
                buttons.append(types.InlineKeyboardButton(category_name, callback_data=callback_data))
            for i in range(0, len(buttons), 2):
                markup.row(*buttons[i:i+2])
            markup.add(types.InlineKeyboardButton('Назад', callback_data='back_to_main_menu'))
            cursor.close()
            connection.close()
        return markup
    except Exception as e:
        logger.error(f"Error in generate_categories_markup: {e}", exc_info=True)
        return types.InlineKeyboardMarkup()


def get_profile_text(user_id):
    connection = create_connection()
    if connection:
        cursor = connection.cursor()
        cursor.execute("SELECT registration_date, rating, correct_answers_count, incorrect_answers_count, show_nickname, show_correct_answers FROM users WHERE user_id = %s", (user_id,))
        profile = cursor.fetchone()
        cursor.execute("SELECT COUNT(*) FROM questions WHERE user_id = %s", (user_id,))
        question_count = cursor.fetchone()['COUNT(*)']
        cursor.execute("SELECT COUNT(*) FROM complaints WHERE user_id = %s", (user_id,))
        complaint_count = cursor.fetchone()['COUNT(*)']
        cursor.close()
        connection.close()

        if profile:
            registration_date, rating, correct_answers_count, incorrect_answers_count, show_nickname, show_correct_answers = profile.values()
            show_nickname_text = "Да" if show_nickname else "Нет"
            show_correct_answers_text = "Да" if show_correct_answers else "Нет"
            profile_text = (
                f"Дата регистрации: {registration_date}\n"
                f"Рейтинг: {rating}\n"
                f"Правильные ответы: {correct_answers_count}\n"
                f"Неправильные ответы: {incorrect_answers_count}\n"
                f"Показывать псевдоним: {show_nickname_text}\n"
                f"Показывать решенное: {show_correct_answers_text}\n"
                f"Количество вопросов: {question_count}\n"
                f"Количество жалоб: {complaint_count}"
            )
            return profile_text, show_nickname, show_correct_answers
    return None, None, None

def send_message(chat_id, text, reply_markup=None, parse_mode=None, is_complaint_confirmation=False):
    try:
        message = bot.send_message(chat_id, text, reply_markup=reply_markup, parse_mode=parse_mode)
        if chat_id not in user_messages:
            user_messages[chat_id] = []
        
        if is_complaint_confirmation:
            for i, (msg_type, msg_id) in enumerate(user_messages[chat_id]):
                if msg_type == "complaint_confirmation":
                    delete_message(chat_id, msg_id)
                    user_messages[chat_id].pop(i)
                    break
            user_messages[chat_id].append(("complaint_confirmation", message.message_id))
        else:
            user_messages[chat_id].append(("message", message.message_id))
        return message
    except Exception as e:
        logger.error(f"Error sending message: {e}", exc_info=True)
# Обработчик кнопки "Назад" в главном меню
@bot.message_handler(func=lambda message: message.text == 'Назад')
def handle_back_in_main_menu(message):
    send_message(message.chat.id, "<B>Айтишечка Квиз Бот</B>\nДобро пожаловать бот работает в тестовом режиме:", reply_markup=generate_inline_main_menu())

# Обработчик выбора категории
@bot.callback_query_handler(func=lambda call: call.data.startswith('category_'))
def handle_category_choice(call):
    try:
        category_hash = call.data.split('_', 1)[1]
        connection = create_connection()
        if connection:
            cursor = connection.cursor()
            cursor.execute("SELECT category_name FROM categories")
            categories = cursor.fetchall()
            category_name = None
            for category in categories:
                if hashlib.md5(category['category_name'].encode()).hexdigest() == category_hash:
                    category_name = category['category_name']
                    break
            if category_name:
                cursor.execute("SELECT category_id FROM categories WHERE category_name = %s", (category_name,))
                category_id = cursor.fetchone()
                if category_id:
                    category_id = category_id['category_id']
                    user_id = get_user_id(call.from_user.id)
                    set_user_category(user_id, category_id)  # Устанавливаем текущую категорию для пользователя
                    delete_all_messages(call.message.chat.id)  # Удаляем все сообщения перед отображением сложности
                    send_message(call.message.chat.id, "Выберите сложность:", reply_markup=generate_difficulty_markup(category_id, user_id))
                else:
                    send_message(call.message.chat.id, "Категория не найдена.", reply_markup=generate_inline_main_menu())
            else:
                send_message(call.message.chat.id, "Категория не найдена.", reply_markup=generate_inline_main_menu())
            cursor.close()
            connection.close()
    except Exception as e:
        logger.error(f"Error in handle_category_choice: {e}", exc_info=True)
        send_message(call.message.chat.id, "Произошла ошибка. Пожалуйста, попробуйте снова.")

def count_available_questions(category_id, difficulty, user_id):
    connection = create_connection()
    cursor = connection.cursor()

    # Получаем настройки пользователя
    cursor.execute("SELECT show_correct_answers FROM users WHERE user_id = %s", (user_id,))
    settings = cursor.fetchone()

    if settings and settings['show_correct_answers']:
        query = """
            SELECT COUNT(*)
            FROM questions q
            WHERE q.category_id = %s AND q.difficulty_id = %s AND q.moderation_status = True
        """
        cursor.execute(query, (category_id, difficulty))
    else:
        query = """
            SELECT COUNT(*)
            FROM questions q
            LEFT JOIN passedquestions pq ON q.question_id = pq.question_id AND pq.user_id = %s
            WHERE q.category_id = %s AND q.difficulty_id = %s AND q.moderation_status = True AND pq.question_id IS NULL
        """
        cursor.execute(query, (user_id, category_id, difficulty))

    count = cursor.fetchone()['COUNT(*)']
    cursor.close()
    connection.close()
    return count
# Генерация меню выбора сложности
def generate_difficulty_markup(category_id, user_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    difficulties = [('1', 'Легкая'), ('2', 'Средняя'), ('3', 'Тяжелая')]

    for difficulty, label in difficulties:
        count = count_available_questions(category_id, difficulty, user_id)
        callback_data = f'difficulty_{category_id}_{difficulty}'
        markup.add(types.InlineKeyboardButton(f'{label} ({count})', callback_data=callback_data))
    
    # Получаем общее количество вопросов для случайной сложности
    total_count = count_total_questions(category_id)
    markup.add(types.InlineKeyboardButton(f'Случайная сложность ({total_count})', callback_data=f'difficulty_{category_id}_random'))
    markup.add(types.InlineKeyboardButton('Назад', callback_data='back_to_main_menu'))
    return markup

def count_total_questions(category_id):
    try:
        connection = create_connection()
        if connection:
            cursor = connection.cursor()
            query = """
                SELECT COUNT(*)
                FROM questions q
                WHERE q.category_id = %s AND q.moderation_status = True
            """
            cursor.execute(query, (category_id,))
            count = cursor.fetchone()['COUNT(*)']
            cursor.close()
            connection.close()
            return count
    except Exception as e:
        logger.error(f"Error in count_total_questions: {e}", exc_info=True)
        return 0
        
def generate_inline_main_menu():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(types.InlineKeyboardButton('Категории', callback_data='categories'),
               types.InlineKeyboardButton('Профиль', callback_data='profile'))
    markup.add(types.InlineKeyboardButton('Админка', callback_data='admin'),
               types.InlineKeyboardButton('Добавить вопрос', callback_data='add_question'))
    markup.add(types.InlineKeyboardButton('Донат', callback_data='donate'))
    return markup

@bot.callback_query_handler(func=lambda call: call.data in ['categories', 'profile', 'admin', 'add_question', 'donate'])
def handle_main_menu_callbacks(call):
    user_id = get_user_id(call.from_user.id)
    if not user_id:
        register_user(call.from_user.id)
        user_id = get_user_id(call.from_user.id)

    if call.data == 'categories':
        delete_all_messages(call.message.chat.id)  # Удаляем главное меню перед отображением категорий
        send_message(call.message.chat.id, "Выберите категорию:", reply_markup=generate_categories_markup())
    elif call.data == 'profile':
        show_profile_without_menu(call)
    elif call.data == 'admin':
        send_message(call.message.chat.id, "Админка (функционал в разработке).")
    elif call.data == 'add_question':
        send_message(call.message.chat.id, "Напишите свой вопрос:")
        bot.register_next_step_handler(call.message, handle_question_input)
    elif call.data == 'donate':
        send_message(call.message.chat.id, "Принимаем перевод на карту: 2202206264599551 (На оплату сервера, чая и печенек).")
        
def handle_question_input(message):
    try:
        user_id = get_user_id(message.from_user.id)
        user_questions[user_id] = {'question_text': message.text}
        send_message(message.chat.id, "Напишите первый вариант ответа:")
        bot.register_next_step_handler(message, handle_first_option_input)
    except Exception as e:
        logger.error(f"Error in handle_question_input: {e}", exc_info=True)
        send_message(message.chat.id, "Произошла ошибка. Пожалуйста, попробуйте снова.")

def handle_first_option_input(message):
    try:
        user_id = get_user_id(message.from_user.id)
        user_questions[user_id]['option1'] = message.text
        send_message(message.chat.id, "Напишите второй вариант ответа:")
        bot.register_next_step_handler(message, handle_second_option_input)
    except Exception as e:
        logger.error(f"Error in handle_first_option_input: {e}", exc_info=True)
        send_message(message.chat.id, "Произошла ошибка. Пожалуйста, попробуйте снова.")

def handle_second_option_input(message):
    try:
        user_id = get_user_id(message.from_user.id)
        user_questions[user_id]['option2'] = message.text
        send_message(message.chat.id, "Напишите третий вариант ответа:")
        bot.register_next_step_handler(message, handle_third_option_input)
    except Exception as e:
        logger.error(f"Error in handle_second_option_input: {e}", exc_info=True)
        send_message(message.chat.id, "Произошла ошибка. Пожалуйста, попробуйте снова.")

def handle_third_option_input(message):
    try:
        user_id = get_user_id(message.from_user.id)
        user_questions[user_id]['option3'] = message.text
        send_message(message.chat.id, "Напишите четвертый вариант ответа:")
        bot.register_next_step_handler(message, handle_fourth_option_input)
    except Exception as e:
        logger.error(f"Error in handle_third_option_input: {e}", exc_info=True)
        send_message(message.chat.id, "Произошла ошибка. Пожалуйста, попробуйте снова.")

def handle_fourth_option_input(message):
    try:
        user_id = get_user_id(message.from_user.id)
        user_questions[user_id]['option4'] = message.text
        send_message(message.chat.id, "Напишите номер правильного ответа (1, 2, 3 или 4):")
        bot.register_next_step_handler(message, handle_correct_option_input)
    except Exception as e:
        logger.error(f"Error in handle_fourth_option_input: {e}", exc_info=True)
        send_message(message.chat.id, "Произошла ошибка. Пожалуйста, попробуйте снова.")

def handle_correct_option_input(message):
    try:
        user_id = get_user_id(message.from_user.id)
        correct_option = message.text
        if correct_option in ['1', '2', '3', '4']:
            user_questions[user_id]['correct_option'] = correct_option
            send_message(message.chat.id, "Выберите уровень сложности вопроса (1 - Легкий, 2 - Средний, 3 - Сложный):")
            bot.register_next_step_handler(message, handle_difficulty_input)
        else:
            send_message(message.chat.id, "Пожалуйста, введите корректный номер (1, 2, 3 или 4):")
            bot.register_next_step_handler(message, handle_correct_option_input)
    except Exception as e:
        logger.error(f"Error in handle_correct_option_input: {e}", exc_info=True)
        send_message(message.chat.id, "Произошла ошибка. Пожалуйста, попробуйте снова.")

def handle_category_input(message):
    try:
        user_id = get_user_id(message.from_user.id)
        category_name = message.text
        connection = create_connection()
        if connection:
            cursor = connection.cursor()
            cursor.execute("SELECT category_id FROM categories WHERE category_name = %s", (category_name,))
            category = cursor.fetchone()
            if category:
                user_questions[user_id]['category_id'] = category['category_id']
                save_question_to_moderation(user_questions[user_id], user_id, message.chat.id)
                send_message(message.chat.id, "Ваш вопрос отправлен на модерацию.", reply_markup=generate_inline_main_menu())
                del user_questions[user_id]  # Очистка данных пользователя
            else:
                send_message(message.chat.id, "Категория не найдена, попробуйте снова:")
                bot.register_next_step_handler(message, handle_category_input)
            cursor.close()
            connection.close()
    except Exception as e:
        logger.error(f"Error in handle_category_input: {e}", exc_info=True)
        send_message(message.chat.id, "Произошла ошибка. Пожалуйста, попробуйте снова.")

def handle_difficulty_input(message):
    try:
        user_id = get_user_id(message.from_user.id)
        difficulty = message.text
        if difficulty in ['1', '2', '3']:
            user_questions[user_id]['difficulty_id'] = difficulty
            send_message(message.chat.id, "Выберите категорию вопроса:", reply_markup=generate_categories_markup_for_question())
        else:
            send_message(message.chat.id, "Пожалуйста, введите корректный уровень сложности (1, 2 или 3):")
            bot.register_next_step_handler(message, handle_difficulty_input)
    except Exception as e:
        logger.error(f"Error in handle_difficulty_input: {e}", exc_info=True)
        send_message(message.chat.id, "Произошла ошибка. Пожалуйста, попробуйте снова.")

@bot.callback_query_handler(func=lambda call: call.data.startswith('category_question_'))
def handle_category_select(call):
    try:
        # Логируем исходный call.data для отладки
        logger.info(f"Callback data received: {call.data}")
        
        # Парсим category_id
        category_id = call.data.split('_')[2]
        logger.info(f"Parsed category_id: {category_id}")
        
        user_id = get_user_id(call.from_user.id)
        logger.info(f"User ID: {user_id}")
        
        if user_id in user_questions:
            user_questions[user_id]['category_id'] = category_id
            delete_last_message(call.message.chat.id)
            save_question_to_moderation(user_questions[user_id], user_id, call.message.chat.id)
            send_message(call.message.chat.id, "Ваш вопрос отправлен на модерацию.", reply_markup=generate_inline_main_menu())
            del user_questions[user_id]
        else:
            logger.info(f"Question data not found for user_id: {user_id}")
            send_message(call.message.chat.id, "Не удалось найти вопрос для пользователя. Попробуйте снова.")
    except Exception as e:
        logger.error(f"Error in handle_category_select: {e}", exc_info=True)
        send_message(call.message.chat.id, "Произошла ошибка. Пожалуйста, попробуйте снова.")
@bot.callback_query_handler(func=lambda call: call.data == 'add_question')
def handle_add_question(call):
    delete_last_message(call.message.chat.id)
    send_message(call.message.chat.id, "Напишите свой вопрос:")
    bot.register_next_step_handler(call.message, handle_question_input)

def generate_categories_markup_for_question():
    try:
        markup = types.InlineKeyboardMarkup(row_width=2)
        connection = create_connection()
        if connection:
            cursor = connection.cursor()
            cursor.execute("SELECT category_id, category_name FROM categories")
            categories = cursor.fetchall()
            buttons = []
            for category in categories:
                category_id = category['category_id']
                category_name = category['category_name']
                callback_data = f'category_question_{category_id}'
                logger.info(f"Adding button: {category_name} with callback_data: {callback_data}")
                buttons.append(types.InlineKeyboardButton(category_name, callback_data=callback_data))
            for i in range(0, len(buttons), 2):
                markup.row(*buttons[i:i+2])
            cursor.close()
            connection.close()
        return markup
    except Exception as e:
        logger.error(f"Error in generate_categories_markup_for_question: {e}", exc_info=True)
        return types.InlineKeyboardMarkup()
def save_question_to_moderation(question_data, user_id, chat_id):
    try:
        connection = create_connection()
        if connection:
            cursor = connection.cursor()
            cursor.execute("SELECT user_id FROM users WHERE user_id = %s", (user_id,))
            user = cursor.fetchone()
            if not user:
                logger.info(f"User not found: {user_id}")
                send_message(chat_id, "Пользователь не найден. Попробуйте зарегистрироваться снова.")
                return

            logger.info(f"Saving question: {question_data}")
            cursor.execute("""
                INSERT INTO questions (question_text, option1, option2, option3, option4, correct_option, user_id, difficulty_id, category_id, moderation_status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                question_data['question_text'],
                question_data['option1'],
                question_data['option2'],
                question_data['option3'],
                question_data['option4'],
                question_data['correct_option'],
                user_id,
                question_data['difficulty_id'],
                question_data['category_id'],
                False  # Вопрос отправляется на модерацию
            ))
            connection.commit()
            logger.info(f"Question saved: {question_data}, User ID: {user_id}")
            send_message(chat_id, "Ваш вопрос отправлен на модерацию.", reply_markup=generate_inline_main_menu())
            cursor.close()
            connection.close()
    except pymysql.MySQLError as err:
        logger.error(f"Error in save_question_to_moderation: {err}", exc_info=True)
        send_message(chat_id, "Произошла ошибка при сохранении вопроса. Попробуйте еще раз.")
# Генерация инлайн-кнопок для информации о вопросе
def generate_info_markup(question_id):
    markup = types.InlineKeyboardMarkup(row_width=3)
    markup.add(types.InlineKeyboardButton("Главная", callback_data='back_to_main_menu'),
               types.InlineKeyboardButton("Пропустить", callback_data=f'skip_question_{question_id}'),
               types.InlineKeyboardButton("Жалоба", callback_data=f'complaint_{question_id}'))
    return markup

# Генерация инлайн-кнопок для вопросов
def generate_question_markup(question):
    question_id, question_text, option1, option2, option3, option4, correct_option, user_id, correct_answers_count, incorrect_answers_count, difficulty_id, category, username, show_nickname = question.values()
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(types.InlineKeyboardButton(option1, callback_data=f'answer_{question_id}_{correct_option}_1'))
    markup.add(types.InlineKeyboardButton(option2, callback_data=f'answer_{question_id}_{correct_option}_2'))
    markup.add(types.InlineKeyboardButton(option3, callback_data=f'answer_{question_id}_{correct_option}_3'))
    markup.add(types.InlineKeyboardButton(option4, callback_data=f'answer_{question_id}_{correct_option}_4'))
    return markup

# Обновление обработчика выбора сложности
@bot.callback_query_handler(func=lambda call: call.data.startswith('difficulty_'))
def handle_difficulty_choice(call):
    try:
        category_id, difficulty_id = call.data.split('_')[1:]
        user_id = get_user_id(call.from_user.id)

        delete_all_messages(call.message.chat.id)  # Удаляем сообщения при выборе сложности

        question = get_random_question(category_id, user_id, difficulty_id)
        if question:
            question_id, question_text, option1, option2, option3, option4, correct_option, question_user_id, correct_answers_count, incorrect_answers_count, difficulty_id, category, username, show_nickname = question.values()

            if show_nickname:
                author_info = username
            else:
                author_info = "Автор скрыт"

            # Проверяем, был ли вопрос уже пройден пользователем
            passed = has_user_answered_question(user_id, question_id)
            passed_status = "Пройден" if passed else "Не пройден"

            question_info = (
                f"ID вопроса: {question_id}\n"
                f"Автор: {author_info}\n"
                f"Успешно прошли: {correct_answers_count}\n"
                f"Завалили: {incorrect_answers_count}\n"
                f"Сложность: {difficulty_id}\n"
                f"Категория: {category}\n"
                f"Статус: {passed_status}\n\n"
            )
            send_message(call.message.chat.id, question_info, reply_markup=generate_info_markup(question_id), parse_mode="html")
            send_message(call.message.chat.id, question_text, reply_markup=generate_question_markup(question))
        else:
            send_message(call.message.chat.id, "Все вопросы в данной категории и с указанной сложностью закончились. (Вы всегда можете включить в настройках пройденные тесты, но за них не идет репутация)", reply_markup=generate_inline_main_menu())
    except Exception as e:
        logger.error(f"Error in handle_difficulty_choice: {e}", exc_info=True)
        send_message(call.message.chat.id, "Произошла ошибка. Пожалуйста, попробуйте снова.")

# Обновление обработчика ответа на вопрос
@bot.callback_query_handler(func=lambda call: call.data.startswith('answer_'))
def handle_question_answer(call):
    try:
        question_id, correct_option, selected_option = call.data.split('_')[1:]
        user_id = get_user_id(call.from_user.id)

        # Получаем вопрос и проверяем правильность ответа
        connection = create_connection()
        cursor = connection.cursor()
        cursor.execute("SELECT question_text, option1, option2, option3, option4 FROM questions WHERE question_id = %s", (question_id,))
        question = cursor.fetchone()
        cursor.close()
        connection.close()

        if question:
            question_text, option1, option2, option3, option4 = question.values()
            options = [option1, option2, option3, option4]
            user_answer_text = options[int(selected_option) - 1]

            if correct_option == selected_option:
                bot.answer_callback_query(call.id, "Правильный ответ!")
                answer_feedback = f"Ваш ответ: {user_answer_text}\nОтвет правильный!"
                reputation_change = get_reputation_change(user_id, question_id, correct=True)
            else:
                bot.answer_callback_query(call.id, "Неправильный ответ.")
                answer_feedback = f"Ваш ответ: {user_answer_text}\nОтвет неправильный."
                reputation_change = get_reputation_change(user_id, question_id, correct=False)

            feedback_message = (
                f"Вопрос: {question_text}\n\n"
                f"{answer_feedback}\n\n"
                f"Репутация изменена на: {reputation_change}"
            )

            # Отправляем сообщение с результатом и кнопками
            feedback_msg = send_message(call.message.chat.id, feedback_message, reply_markup=generate_result_markup())
            
            # Сохраняем ID нового сообщения как "feedback"
            if call.message.chat.id not in user_messages:
                user_messages[call.message.chat.id] = []
            user_messages[call.message.chat.id].append(("feedback", feedback_msg.message_id))
        else:
            send_message(call.message.chat.id, "Произошла ошибка. Пожалуйста, попробуйте снова.")
    except Exception as e:
        logger.error(f"Error in handle_question_answer: {e}", exc_info=True)
        send_message(call.message.chat.id, "Произошла ошибка. Пожалуйста, попробуйте снова.")
def generate_result_markup():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("На главную", callback_data="back_to_main_menu"),
        types.InlineKeyboardButton("Следующий вопрос", callback_data="next_question")
    )
    return markup
@bot.callback_query_handler(func=lambda call: call.data == 'next_question')
def handle_next_question(call):
    try:
        user_id = get_user_id(call.from_user.id)
        last_question_id = get_last_question_id(user_id)
        difficulty_id = get_question_difficulty(last_question_id)

        # Удаление всех сообщений, включая текущий вопрос и статус
        delete_all_messages(call.message.chat.id)

        send_next_question(call.message, user_id, difficulty_id)
    except Exception as e:
        logger.error(f"Error in handle_next_question: {e}", exc_info=True)
        send_message(call.message.chat.id, "Произошла ошибка. Пожалуйста, попробуйте снова.")
        
def get_reputation_change(user_id, question_id, correct):
    connection = create_connection()
    cursor = connection.cursor()
    
    cursor.execute("SELECT difficulty_id FROM questions WHERE question_id = %s", (question_id,))
    difficulty = cursor.fetchone()['difficulty_id']

    if correct:
        cursor.execute("UPDATE users SET correct_answers_count = correct_answers_count + 1, rating = rating + %s WHERE user_id = %s", (difficulty, user_id))
        change = difficulty
    else:
        cursor.execute("UPDATE users SET incorrect_answers_count = incorrect_answers_count + 1, rating = rating - 1 WHERE user_id = %s", (user_id,))
        change = -1

    cursor.execute("INSERT INTO passedquestions (user_id, question_id, passed_at) VALUES (%s, %s, %s)", (user_id, question_id, datetime.now()))
    connection.commit()
    cursor.close()
    connection.close()
    
    return change

def get_question_difficulty(question_id):
    connection = create_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT difficulty_id FROM questions WHERE question_id = %s", (question_id,))
    difficulty_id = cursor.fetchone()['difficulty_id']
    cursor.close()
    connection.close()
    return difficulty_id
def send_next_question(message, user_id, difficulty_id):
    try:
        connection = create_connection()
        if connection:
            cursor = connection.cursor()
            category_id = get_user_category(user_id)
            if category_id:
                question = get_random_question(category_id, user_id, difficulty_id)
                if question:
                    question_id, question_text, option1, option2, option3, option4, correct_option, question_user_id, correct_answers_count, incorrect_answers_count, difficulty_id, category, username, show_nickname = question.values()

                    if show_nickname:
                        author_info = username
                    else:
                        author_info = "Автор скрыт"

                    # Проверяем, был ли вопрос уже пройден пользователем
                    passed = has_user_answered_question(user_id, question_id)
                    passed_status = "Пройден" if passed else "Не пройден"

                    question_info = (
                        f"ID вопроса: {question_id}\n"
                        f"Автор: {author_info}\n"
                        f"Успешно прошли: {correct_answers_count}\n"
                        f"Завалили: {incorrect_answers_count}\n"
                        f"Сложность: {difficulty_id}\n"
                        f"Категория: {category}\n"
                        f"Статус: {passed_status}\n\n"
                    )

                    # Удаляем предыдущее сообщение о жалобе, если есть
                    for i, (msg_type, msg_id) in enumerate(user_messages.get(message.chat.id, [])):
                        if msg_type == "complaint_confirmation":
                            delete_message(message.chat.id, msg_id)
                            user_messages[message.chat.id].pop(i)
                            break

                    # Отправляем информацию о вопросе и сохраняем как "question_info"
                    question_info_msg = send_message(message.chat.id, question_info, reply_markup=generate_info_markup(question_id))
                    # Отправляем сам вопрос и варианты ответа и сохраняем как "question"
                    question_msg = send_message(message.chat.id, question_text, reply_markup=generate_question_markup(question))

                    # Сохраняем ID новых сообщений как "question_info" и "question"
                    if message.chat.id not in user_messages:
                        user_messages[message.chat.id] = []
                    user_messages[message.chat.id].append(("question_info", question_info_msg.message_id))
                    user_messages[message.chat.id].append(("question", question_msg.message_id))
                else:
                    send_message(message.chat.id, "Все вопросы в данной категории и с указанной сложностью закончились. Попробуйте другую категорию.", reply_markup=generate_inline_main_menu())
            else:
                send_message(message.chat.id, "Не удалось найти текущую категорию пользователя.", reply_markup=generate_inline_main_menu())
            cursor.close()
            connection.close()
    except Exception as e:
        logger.error(f"Error in send_next_question: {e}", exc_info=True)
        send_message(message.chat.id, "Произошла ошибка. Пожалуйста, попробуйте снова.")

def generate_complaint_confirmation_markup():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("На главную", callback_data="back_to_main_menu"),
        types.InlineKeyboardButton("К вопросам", callback_data="back_to_questions")
    )
    return markup



# Обновление статистики пользователя
def update_user_stats(user_id, question_id, correct):
    if not has_user_answered_question(user_id, question_id):
        connection = create_connection()
        cursor = connection.cursor()
        
        # Получаем сложность вопроса
        cursor.execute("SELECT difficulty_id FROM questions WHERE question_id = %s", (question_id,))
        difficulty = cursor.fetchone()['difficulty_id']

        # Увеличиваем или уменьшаем репутацию в зависимости от сложности вопроса
        if correct:
            cursor.execute("UPDATE users SET correct_answers_count = correct_answers_count + 1, rating = rating + %s WHERE user_id = %s", (difficulty, user_id))
        else:
            cursor.execute("UPDATE users SET incorrect_answers_count = incorrect_answers_count + 1, rating = rating - 1 WHERE user_id = %s", (user_id,))

        cursor.execute("INSERT INTO passedquestions (user_id, question_id, passed_at) VALUES (%s, %s, %s)", (user_id, question_id, datetime.now()))
        connection.commit()
        cursor.close()
        connection.close()

# Обновление статистики вопросов
def update_question_stats(question_id, correct):
    connection = create_connection()
    cursor = connection.cursor()
    if correct:
        cursor.execute("UPDATE questions SET correct_answers_count = correct_answers_count + 1 WHERE question_id = %s", (question_id,))
    else:
        cursor.execute("UPDATE questions SET incorrect_answers_count = incorrect_answers_count + 1 WHERE question_id = %s", (question_id,))
    connection.commit()
    cursor.close()
    connection.close()

# Получение случайного вопроса из указанной категории
def get_random_question(category_id, user_id, difficulty_id):
    connection = create_connection()
    cursor = connection.cursor()

    # Получаем настройки пользователя
    cursor.execute("SELECT show_correct_answers FROM users WHERE user_id = %s", (user_id,))
    settings = cursor.fetchone()

    # Подготовка запроса в зависимости от режима сложности
    if difficulty_id == 'random':
        difficulty_condition = ""
    else:
        difficulty_condition = "AND q.difficulty_id = %s"

    # Изменяем запрос в зависимости от настроек пользователя
    if settings and settings['show_correct_answers']:
        # Включая пройденные вопросы
        query = f"""
            SELECT q.question_id, q.question_text, q.option1, q.option2, q.option3, q.option4, q.correct_option, q.user_id, q.correct_answers_count, q.incorrect_answers_count, q.difficulty_id, c.category_name, u.username, u.show_nickname 
            FROM questions q
            JOIN categories c ON q.category_id = c.category_id 
            JOIN users u ON q.user_id = u.user_id
            WHERE q.category_id = %s AND q.moderation_status = True {difficulty_condition}
            ORDER BY RAND() LIMIT 1
        """
        if difficulty_id == 'random':
            cursor.execute(query, (category_id,))
        else:
            cursor.execute(query, (category_id, difficulty_id))
    else:
        # Исключая пройденные вопросы
        query = f"""
            SELECT q.question_id, q.question_text, q.option1, q.option2, q.option3, q.option4, q.correct_option, q.user_id, q.correct_answers_count, q.incorrect_answers_count, q.difficulty_id, c.category_name, u.username, u.show_nickname 
            FROM questions q
            JOIN categories c ON q.category_id = c.category_id 
            JOIN users u ON q.user_id = u.user_id
            LEFT JOIN passedquestions pq ON q.question_id = pq.question_id AND pq.user_id = %s
            WHERE q.category_id = %s AND q.moderation_status = True AND pq.question_id IS NULL {difficulty_condition}
            ORDER BY RAND() LIMIT 1
        """
        if difficulty_id == 'random':
            cursor.execute(query, (user_id, category_id))
        else:
            cursor.execute(query, (user_id, category_id, difficulty_id))

    question = cursor.fetchone()
    cursor.close()
    connection.close()
    return question

def get_user_settings(user_id):
    connection = create_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT show_nickname, show_correct_answers FROM users WHERE user_id = %s", (user_id,))
    settings = cursor.fetchone()
    cursor.close()
    connection.close()
    return settings

# Обновление настройки "Показывать ник" в базе данных
def update_show_nickname_setting(user_id, show_nickname):
    connection = create_connection()
    cursor = connection.cursor()
    cursor.execute("UPDATE users SET show_nickname = %s WHERE user_id = %s", (show_nickname, user_id))
    connection.commit()
    cursor.close()
    connection.close()

# Обновление настройки "Показывать верные ответы" в базе данных
def update_show_correct_answers_setting(user_id, show_correct_answers):
    connection = create_connection()
    cursor = connection.cursor()
    cursor.execute("UPDATE users SET show_correct_answers = %s WHERE user_id = %s", (show_correct_answers, user_id))
    connection.commit()
    cursor.close()
    connection.close()

@bot.callback_query_handler(func=lambda call: call.data == 'categories')
def handle_categories(call):
    try:
        delete_all_messages(call.message.chat.id)  # Удаляем все сообщения перед отображением категорий
        send_message(call.message.chat.id, "Выберите категорию:", reply_markup=generate_categories_markup())
    except Exception as e:
        logger.error(f"Error in handle_categories: {e}", exc_info=True)
        send_message(call.message.chat.id, "Произошла ошибка. Пожалуйста, попробуйте снова.")

@bot.callback_query_handler(func=lambda call: call.data.startswith('toggle_'))
def handle_toggle_setting(call):
    user_id = get_user_id(call.from_user.id)
    current_settings = get_user_settings(user_id)
    if call.data == 'toggle_nickname':
        update_show_nickname_setting(user_id, not current_settings['show_nickname'])
    elif call.data == 'toggle_correct_answers':
        update_show_correct_answers_setting(user_id, not current_settings['show_correct_answers'])
    bot.answer_callback_query(call.id, "Настройки обновлены.")
    update_profile_message(call)

# Обработчик нажатия на кнопку "Главная" в профиле
@bot.callback_query_handler(func=lambda call: call.data == 'back_to_main_menu')
def handle_back_to_main_menu(call):
    try:
        chat_id = call.message.chat.id
        delete_all_messages(chat_id)
        send_message(chat_id, "<B>Айтишечка Квиз Бот</B>\nДобро пожаловать бот работает в тестовом режиме:", reply_markup=generate_inline_main_menu(), parse_mode="html")
    except Exception as e:
        logger.error(f"Error in handle_back_to_main_menu: {e}", exc_info=True)
        send_message(chat_id, "Произошла ошибка. Пожалуйста, попробуйте снова.")
def set_user_category(user_id, category_id):
    try:
        connection = create_connection()
        if connection:
            cursor = connection.cursor()
            cursor.execute("UPDATE users SET current_category_id = %s WHERE user_id = %s", (category_id, user_id))
            connection.commit()
            cursor.close()
            connection.close()
    except Exception as e:
        logger.error(f"Error in set_user_category: {e}", exc_info=True)

def get_user_category(user_id):
    try:
        connection = create_connection()
        if connection:
            cursor = connection.cursor()
            cursor.execute("SELECT current_category_id FROM users WHERE user_id = %s", (user_id,))
            category_id = cursor.fetchone()
            cursor.close()
            connection.close()
            return category_id['current_category_id'] if category_id else None
    except Exception as e:
        logger.error(f"Error in get_user_category: {e}", exc_info=True)
        return None

# Обработчик нажатия на кнопку "Пропустить"
@bot.callback_query_handler(func=lambda call: call.data.startswith('skip_question_'))
def handle_skip_question(call):
    try:
        user_id = get_user_id(call.from_user.id)
        last_question_id = call.data.split('_')[2]
        difficulty_id = get_question_difficulty(last_question_id)

        # Удаление кнопок "Жалоба", "Пропустить", "Главная"
        delete_all_messages(call.message.chat.id)

        send_next_question(call.message, user_id, difficulty_id)
    except Exception as e:
        logger.error(f"Error in handle_skip_question: {e}", exc_info=True)
        send_message(call.message.chat.id, "Произошла ошибка. Пожалуйста, попробуйте снова.")
def get_last_question_id(user_id):
    try:
        connection = create_connection()
        if connection:
            cursor = connection.cursor()
            cursor.execute("SELECT question_id FROM passedquestions WHERE user_id = %s ORDER BY passed_at DESC LIMIT 1", (user_id,))
            last_question_id = cursor.fetchone()
            cursor.close()
            connection.close()
            return last_question_id['question_id'] if last_question_id else None
    except Exception as e:
        logger.error(f"Error in get_last_question_id: {e}", exc_info=True)
        return None
# Профиль

def generate_profile_markup_without_menu(show_nickname, show_correct_answers):
    markup = types.InlineKeyboardMarkup(row_width=2)
    show_nickname_button_text = "Скрыть псевдоним" if show_nickname else "Показывать псевдоним"
    show_correct_answers_button_text = "Не показывать решенное" if show_correct_answers else "Показывать решенное"
    show_nickname_button = types.InlineKeyboardButton(show_nickname_button_text, callback_data='toggle_nickname')
    show_correct_answers_button = types.InlineKeyboardButton(show_correct_answers_button_text, callback_data='toggle_correct_answers')
    back_button = types.InlineKeyboardButton("Главная", callback_data='back_to_main_menu')
    markup.add(show_nickname_button, show_correct_answers_button)
    markup.add(back_button)
    return markup

def update_profile_message(call):
    try:
        user_id = get_user_id(call.from_user.id)
        profile_text, show_nickname, show_correct_answers = get_profile_text(user_id)
        if profile_text:
            delete_all_messages(call.message.chat.id)
            send_message(call.message.chat.id, profile_text, reply_markup=generate_profile_markup_without_menu(show_nickname, show_correct_answers))
    except Exception as e:
        logger.error(f"Error in update_profile_message: {e}", exc_info=True)

def show_profile_without_menu(data):
    try:
        if hasattr(data, 'from_user'):
            telegram_id = data.from_user.id
            chat_id = data.message.chat.id
        else:
            telegram_id = data.from_user.id
            chat_id = data.chat.id

        user_id = get_user_id(telegram_id)
        profile_text, show_nickname, show_correct_answers = get_profile_text(user_id)
        if profile_text:
            delete_all_messages(chat_id)
            send_message(chat_id, profile_text, reply_markup=generate_profile_markup_without_menu(show_nickname, show_correct_answers))
    except Exception as e:
        logger.error(f"Error in show_profile_without_menu: {e}", exc_info=True)
        send_message(chat_id, "Произошла ошибка. Пожалуйста, попробуйте снова.")
# Профиль

while True:
    try:
        bot.polling(non_stop=True, interval=0, timeout=20)
    except telebot.apihelper.ApiTelegramException as e:
        if e.error_code == 409:
            logger.error("Conflict detected: another bot instance is running. Exiting.")
            break
        else:
            logger.error(f"Bot polling error: {e}", exc_info=True)
            time.sleep(0.25)
    except Exception as e:
        logger.error(f"Bot polling error: {e}", exc_info=True)
        time.sleep(0.25)
