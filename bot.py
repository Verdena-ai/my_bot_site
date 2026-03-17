import sqlite3
import logging
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
import os
TOKEN = os.environ.get "8779954276:AAG8FIs3yuluNUozM4-hXp0MWp-2oN1SQAQ"
OWNER_PASSWORD = "1234qqq"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

db = sqlite3.connect("v3_plus.db", check_same_thread=False)
cur = db.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    chat_id INTEGER PRIMARY KEY,
    name TEXT,
    username TEXT,
    last_seen TEXT,
    blocked INTEGER DEFAULT 0,
    favorite INTEGER DEFAULT 0,
    note TEXT DEFAULT ''
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
)
""")

db.commit()


# ---------------- БАЗА ----------------

def now_text():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def save_user(chat_id, name="", username=""):
    cur.execute("""
    INSERT INTO users(chat_id, name, username, last_seen)
    VALUES (?, ?, ?, ?)
    ON CONFLICT(chat_id) DO UPDATE SET
        name=excluded.name,
        username=excluded.username,
        last_seen=excluded.last_seen
    """, (chat_id, name or "", username or "", now_text()))
    db.commit()


def set_setting(key, value):
    cur.execute("""
    INSERT INTO settings(key, value)
    VALUES(?, ?)
    ON CONFLICT(key) DO UPDATE SET value=excluded.value
    """, (key, str(value)))
    db.commit()


def get_setting(key):
    cur.execute("SELECT value FROM settings WHERE key=?", (key,))
    row = cur.fetchone()
    return row[0] if row else None


def delete_setting(key):
    cur.execute("DELETE FROM settings WHERE key=?", (key,))
    db.commit()


def get_owner_id():
    value = get_setting("owner_id")
    return int(value) if value else None


def is_owner(chat_id):
    owner_id = get_owner_id()
    return owner_id == chat_id


def set_owner(chat_id):
    set_setting("owner_id", chat_id)


def get_user(chat_id):
    cur.execute("""
    SELECT chat_id, name, username, last_seen, blocked, favorite, note
    FROM users WHERE chat_id=?
    """, (chat_id,))
    return cur.fetchone()


def get_users(limit=15):
    cur.execute("""
    SELECT chat_id, name, username, last_seen, blocked, favorite, note
    FROM users
    ORDER BY last_seen DESC
    LIMIT ?
    """, (limit,))
    return cur.fetchall()


def get_last_user():
    owner_id = get_owner_id()
    if owner_id:
        cur.execute("""
        SELECT chat_id FROM users
        WHERE chat_id != ?
        ORDER BY last_seen DESC
        LIMIT 1
        """, (owner_id,))
    else:
        cur.execute("""
        SELECT chat_id FROM users
        ORDER BY last_seen DESC
        LIMIT 1
        """)
    row = cur.fetchone()
    return row[0] if row else None


def search_users(text, limit=15):
    pattern = f"%{text.strip()}%"
    cur.execute("""
    SELECT chat_id, name, username, last_seen, blocked, favorite, note
    FROM users
    WHERE name LIKE ? OR username LIKE ? OR CAST(chat_id AS TEXT) LIKE ?
    ORDER BY last_seen DESC
    LIMIT ?
    """, (pattern, pattern, pattern, limit))
    return cur.fetchall()


def get_favorites(limit=15):
    cur.execute("""
    SELECT chat_id, name, username, last_seen, blocked, favorite, note
    FROM users
    WHERE favorite=1
    ORDER BY last_seen DESC
    LIMIT ?
    """, (limit,))
    return cur.fetchall()


def count_users():
    cur.execute("SELECT COUNT(*) FROM users")
    return cur.fetchone()[0]


def count_blocked():
    cur.execute("SELECT COUNT(*) FROM users WHERE blocked=1")
    return cur.fetchone()[0]


def count_favorites():
    cur.execute("SELECT COUNT(*) FROM users WHERE favorite=1")
    return cur.fetchone()[0]


def is_blocked(chat_id):
    cur.execute("SELECT blocked FROM users WHERE chat_id=?", (chat_id,))
    row = cur.fetchone()
    return bool(row[0]) if row else False


def toggle_block(chat_id):
    cur.execute("""
    UPDATE users
    SET blocked = CASE WHEN blocked=1 THEN 0 ELSE 1 END
    WHERE chat_id=?
    """, (chat_id,))
    db.commit()


def toggle_favorite(chat_id):
    cur.execute("""
    UPDATE users
    SET favorite = CASE WHEN favorite=1 THEN 0 ELSE 1 END
    WHERE chat_id=?
    """, (chat_id,))
    db.commit()


def set_note(chat_id, text):
    cur.execute("UPDATE users SET note=? WHERE chat_id=?", (text, chat_id))
    db.commit()


# ---------------- МЕНЮ ----------------

def owner_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 Пользователи", callback_data="users")],
        [InlineKeyboardButton("⚡ Последний", callback_data="last")],
        [InlineKeyboardButton("🔎 Поиск", callback_data="search")],
        [InlineKeyboardButton("📊 Статистика", callback_data="stats")],
        [InlineKeyboardButton("⭐ Избранные", callback_data="favorites")],
        [InlineKeyboardButton("⭐ В избранное / убрать", callback_data="toggle_fav")],
        [InlineKeyboardButton("📝 Заметка", callback_data="note")],
        [InlineKeyboardButton("🚫 Бан / разбан", callback_data="ban")],
        [InlineKeyboardButton("🤖 Автоответ", callback_data="auto")],
        [InlineKeyboardButton("❌ Закрыть диалог", callback_data="close_dialog")],
    ])


def user_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("ℹ️ Мой ID", callback_data="my_id")],
        [InlineKeyboardButton("❌ Завершить", callback_data="user_close")]
    ])


def format_user_button(user_row):
    chat_id, name, username, last_seen, blocked, favorite, note = user_row
    uname = f"@{username}" if username else "без username"
    marks = ""
    if blocked:
        marks += " 🚫"
    if favorite:
        marks += " ⭐"
    text = f"{name} | {uname}{marks}"
    return InlineKeyboardButton(text[:60], callback_data=f"pick_{chat_id}")


def build_users_keyboard(rows):
    keyboard = [[format_user_button(row)] for row in rows]
    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="back_menu")])
    return InlineKeyboardMarkup(keyboard)


def selected_text(chat_id):
    target_id = get_setting(f"selected_{chat_id}")
    if not target_id:
        return "Никто не выбран."

    user = get_user(int(target_id))
    if not user:
        return "Выбранный пользователь не найден."

    _, name, username, last_seen, blocked, favorite, note = user
    uname = f"@{username}" if username else "без username"
    return (
        f"Активный собеседник:\n"
        f"Имя: {name}\n"
        f"Username: {uname}\n"
        f"Chat ID: {target_id}\n"
        f"Последний визит: {last_seen}\n"
        f"Бан: {'Да' if blocked else 'Нет'}\n"
        f"Избранное: {'Да' if favorite else 'Нет'}\n"
        f"Заметка: {note if note else 'нет'}"
    )


# ---------------- КОМАНДЫ ----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat_id = update.effective_chat.id

    save_user(chat_id, user.first_name or "", user.username or "")

    if is_owner(chat_id):
        await update.message.reply_text("Панель владельца:", reply_markup=owner_menu())
        return

    if is_blocked(chat_id):
        await update.message.reply_text("Ты заблокирован владельцем бота.")
        return

    await update.message.reply_text(
        f"Привет, {user.first_name or 'друг'}.\n"
        f"Ты зарегистрирован в боте.\n"
        f"Твой chat id: {chat_id}",
        reply_markup=user_menu()
    )

    owner_id = get_owner_id()
    if owner_id and owner_id != chat_id:
        uname = f"@{user.username}" if user.username else "без username"
        try:
            await context.bot.send_message(
                owner_id,
                f"Новый/вернувшийся пользователь:\n"
                f"{user.first_name}\n"
                f"{uname}\n"
                f"ID: {chat_id}",
                reply_markup=owner_menu()
            )
        except Exception:
            pass


async def claim(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Напиши так: /claim 1234")
        return

    if context.args[0] != OWNER_PASSWORD:
        await update.message.reply_text("Пароль неверный.")
        return

    set_owner(update.effective_chat.id)
    await update.message.reply_text("Теперь ты владелец.", reply_markup=owner_menu())


async def end(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    if is_owner(chat_id):
        delete_setting(f"selected_{chat_id}")
        await update.message.reply_text("Диалог закрыт.", reply_markup=owner_menu())
        return

    owner_id = get_owner_id()
    await update.message.reply_text("Ты вышел из диалога.", reply_markup=user_menu())

    if owner_id:
        try:
            await context.bot.send_message(
                owner_id,
                f"Пользователь {chat_id} завершил диалог.",
                reply_markup=owner_menu()
            )
        except Exception:
            pass


# ---------------- CALLBACK ----------------

async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    chat_id = query.message.chat_id
    data = query.data

    if data == "my_id":
        await query.message.reply_text(f"Твой chat id: {chat_id}")
        return

    if data == "user_close":
        await query.message.reply_text("Ты завершил диалог.", reply_markup=user_menu())
        owner_id = get_owner_id()
        if owner_id:
            try:
                await context.bot.send_message(owner_id, f"Пользователь {chat_id} вышел.", reply_markup=owner_menu())
            except Exception:
                pass
        return

    if not is_owner(chat_id):
        await query.message.reply_text("Это меню только для владельца.")
        return

    if data == "back_menu":
        await query.message.reply_text("Главное меню:", reply_markup=owner_menu())
        return

    if data == "users":
        rows = get_users(20)
        if not rows:
            await query.message.reply_text("Пользователей пока нет.")
            return
        await query.message.reply_text("Список пользователей:", reply_markup=build_users_keyboard(rows))
        return

    if data == "last":
        last_id = get_last_user()
        if not last_id:
            await query.message.reply_text("Пользователей пока нет.")
            return

        if last_id == chat_id:
            await query.message.reply_text("Последний пользователь — это ты сам.")
            return

        set_setting(f"selected_{chat_id}", last_id)
        await query.message.reply_text(selected_text(chat_id), reply_markup=owner_menu())
        return

    if data == "search":
        set_setting(f"search_mode_{chat_id}", "1")
        await query.message.reply_text("Напиши имя, username или ID для поиска.")
        return

    if data == "stats":
        active = get_setting(f"selected_{chat_id}")
        text = (
            f"Статистика:\n"
            f"Всего пользователей: {count_users()}\n"
            f"Заблокировано: {count_blocked()}\n"
            f"Избранных: {count_favorites()}\n"
            f"Активный собеседник: {'Есть' if active else 'Нет'}"
        )
        await query.message.reply_text(text, reply_markup=owner_menu())
        return

    if data == "favorites":
        rows = get_favorites(20)
        if not rows:
            await query.message.reply_text("Избранных пока нет.")
            return
        await query.message.reply_text("Избранные:", reply_markup=build_users_keyboard(rows))
        return

    if data == "toggle_fav":
        selected = get_setting(f"selected_{chat_id}")
        if not selected:
            await query.message.reply_text("Сначала выбери пользователя.")
            return

        toggle_favorite(int(selected))
        await query.message.reply_text("Избранное переключено.", reply_markup=owner_menu())
        await query.message.reply_text(selected_text(chat_id), reply_markup=owner_menu())
        return

    if data == "note":
        selected = get_setting(f"selected_{chat_id}")
        if not selected:
            await query.message.reply_text("Сначала выбери пользователя.")
            return

        set_setting(f"note_mode_{chat_id}", selected)
        await query.message.reply_text("Теперь пришли текст заметки одним сообщением.")
        return

    if data == "ban":
        selected = get_setting(f"selected_{chat_id}")
        if not selected:
            await query.message.reply_text("Сначала выбери пользователя.")
            return

        toggle_block(int(selected))
        await query.message.reply_text("Бан переключён.", reply_markup=owner_menu())
        await query.message.reply_text(selected_text(chat_id), reply_markup=owner_menu())
        return

    if data == "auto":
        key = f"auto_reply_{chat_id}"
        current = get_setting(key)
        new_value = "0" if current == "1" else "1"
        set_setting(key, new_value)
        await query.message.reply_text(
            f"Автоответ: {'включён' if new_value == '1' else 'выключен'}",
            reply_markup=owner_menu()
        )
        return

    if data == "close_dialog":
        delete_setting(f"selected_{chat_id}")
        await query.message.reply_text("Активный собеседник снят.", reply_markup=owner_menu())
        return

    if data.startswith("pick_"):
        picked_id = data.replace("pick_", "", 1)
        set_setting(f"selected_{chat_id}", picked_id)
        await query.message.reply_text("Пользователь выбран.", reply_markup=owner_menu())
        await query.message.reply_text(selected_text(chat_id), reply_markup=owner_menu())
        return


# ---------------- СООБЩЕНИЯ ----------------

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user
    text = update.message.text.strip()

    save_user(chat_id, user.first_name or "", user.username or "")

    if is_owner(chat_id):
        if get_setting(f"search_mode_{chat_id}") == "1":
            delete_setting(f"search_mode_{chat_id}")
            rows = search_users(text, 20)

            if not rows:
                await update.message.reply_text("Ничего не найдено.", reply_markup=owner_menu())
                return

            await update.message.reply_text(
                f"Найдено: {len(rows)}",
                reply_markup=build_users_keyboard(rows)
            )
            return

        note_target = get_setting(f"note_mode_{chat_id}")
        if note_target:
            set_note(int(note_target), text)
            delete_setting(f"note_mode_{chat_id}")
            await update.message.reply_text("Заметка сохранена.", reply_markup=owner_menu())
            await update.message.reply_text(selected_text(chat_id), reply_markup=owner_menu())
            return

        selected = get_setting(f"selected_{chat_id}")
        if not selected:
            await update.message.reply_text(
                "Сначала выбери пользователя через меню.",
                reply_markup=owner_menu()
            )
            return

        target_id = int(selected)

        if is_blocked(target_id):
            await update.message.reply_text("Этот пользователь заблокирован.")
            return

        try:
            await context.bot.send_message(
                target_id,
                f"Сообщение от владельца:\n{text}",
                reply_markup=user_menu()
            )
            await update.message.reply_text("Сообщение отправлено.")
        except Exception:
            await update.message.reply_text("Не удалось отправить сообщение.")
        return

    if is_blocked(chat_id):
        await update.message.reply_text("Ты заблокирован владельцем бота.")
        return

    owner_id = get_owner_id()
    if owner_id:
        try:
            await context.bot.send_message(
                owner_id,
                f"Ответ от пользователя {chat_id}:\n{text}",
                reply_markup=owner_menu()
            )
        except Exception:
            pass

    auto_enabled = get_setting(f"auto_reply_{owner_id}") if owner_id else None
    if auto_enabled == "1":
        await update.message.reply_text("Владелец сейчас занят. Ответит позже.", reply_markup=user_menu())


# ---------------- ЗАПУСК ----------------

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("claim", claim))
    app.add_handler(CommandHandler("end", end))
    app.add_handler(CallbackQueryHandler(buttons))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("V3 Plus бот запущен...")
    app.run_polling()


if __name__ == "__main__":
    main()