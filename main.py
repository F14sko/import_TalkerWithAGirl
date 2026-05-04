import sys
import asyncio
from unittest import signals
import aiosqlite
import aiohttp
import os
import json
import re
import threading
import subprocess
from datetime import datetime
from telethon import TelegramClient, events
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QScrollArea, QFrame, QLineEdit, QTextEdit, 
    QDialog
)
from PyQt6.QtCore import Qt, QPropertyAnimation, QRect, QEasingCurve, pyqtSignal, QObject, QTimer, QPoint
from PyQt6.QtGui import QPixmap

CONFIG_FILE = "config.json"
DEFAULT_CONFIG = {
    "API_ID": 0,
    "API_HASH": "",
    "API_KEY": "",
    "MY_BIO": "",
    "PROMPT_INTRO": "ты — остроумный, уверенный в себе парень. Твоя цель — завязать непринужденный диалог. Правила общения: Краткость: Пиши не более 1–2 предложений. Никаких длинных абзацев. Живой язык: Используй современную лексику, но без перебора. Никакой лести: Не делай банальных комплиментов внешности. Используй легкий «пэйсинг» (поддразнивание). Инициатива: Всегда заканчивай ответ коротким открытым вопросом или призывом к действию. Запреты: Не используй фразы «Как прошел твой день?», «Чем занимаешься?», эмодзи-роботов и официальный тон. Правила: Краткость (1-2 предл.), живой язык, никакой лести. Завершай вопросом. ",
    "PROMPT_CHAT": "Ты — парень, который уже нравится этой девушке. Общайся расслабленно, тепло, иногда подкалывай и заигрывай. Тон уверенный, но не пошлый. Пиши коротко, в стиле мессенджеров. Используй контекст ваших шуток из истории. Правила общения: Краткость: Пиши не более 1–2 предложений. Никаких длинных абзацев. Живой язык: Используй современную лексику, но без перебора. Никакой лести: Не делай банальных комплиментов внешности. Инициатива: Всегда заканчивай ответ коротким открытым вопросом или призывом к действию. Запреты: Не используй фразы «Как прошел твой день?», «Чем занимаешься?», эмодзи-роботов и официальный тон. Правила: Краткость (1-2 предл.), живой язык, никакой лести. Завершай вопросом. "
}

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            try:
                return {**DEFAULT_CONFIG, **json.load(f)}
            except:
                return DEFAULT_CONFIG
    return DEFAULT_CONFIG

def save_config(new_conf):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(new_conf, f, indent=4, ensure_ascii=False)

conf = load_config()
DB_PATH = "dating_bot.db"
IMAGE_PATH = "ava.png" 

db = None
client = None
loop = None
pending_tasks = {}

async def call_groq_api(prompt):
    url = "https://api.groq.com/openai/v1/chat/completions"
    
    actual_api_key = conf.get("API_KEY", "")

    headers = {
        "Authorization": f"Bearer {actual_api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "llama-3.1-8b-instant",
        "messages": [
            {"role": "system", "content": "Ты отвечаешь как человек. Коротко, живо, без лишней пунктуации."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.9,
        "max_tokens": 150
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data["choices"][0]["message"]["content"].strip()
                else:
                    text = await resp.text()
                    signals.error_signal.emit(f"ERR_GROQ_{resp.status}")
                    return None
    except Exception as e:
        signals.error_signal.emit("ERR_GROQ_CONNECTION")
        return None

async def generate_ai_summary(text_history):
    prompt = f"Проанализируй переписку и сделай краткий пересказ на русском. Ключевые темы и итоги.\n\nПереписка:\n{text_history}"
    return await call_groq_api(prompt)

async def extract_hobbies(text):
    prompt = f"""
Извлеки хобби из сообщения.

Ответ строго в JSON массиве без лишнего текста.

Пример:
["спорт", "рисование"]

Сообщение:
{text}
"""

    response = await call_groq_api(prompt)

    try:
        hobbies = json.loads(response)
        if isinstance(hobbies, list):
            return [h.strip().lower() for h in hobbies if h.strip()]
    except Exception as e:
        signals.error_signal.emit("ERR_JSON_PARSE")

    return []

def detect_language(text):
    if any(c in text.lower() for c in "абвгдеёжзийклмнопрстуфхцчшщ"):
        return "ru"
    return "en"


async def get_user_language(user_id):
    async with db.execute(
        "SELECT language FROM profiles WHERE user_id=?",
        (user_id,)
    ) as cur:
        row = await cur.fetchone()
        return row[0] if row else None


async def set_user_language(user_id, language):
    await db.execute(
        "UPDATE profiles SET language=? WHERE user_id=?",
        (language, user_id)
    )
    await db.commit()

def clean_text(text):
    return re.sub(r"[^\w\s?.]+", "", text)


def split_sentences(text):
    return [s.strip() for s in text.split('.') if s.strip()]

async def handle_new_message(event):

    if not event.is_private:
        return

    chat_id = event.chat_id

    async with db.execute(
        "SELECT status FROM profiles WHERE user_id=?",
        (chat_id,)
    ) as cur:
        row = await cur.fetchone()

    if not row:
        return  # чата нет вообще

    if row[0] != 'active':
        return


    text = event.message.text or ""


    lang = await get_user_language(chat_id)

    text = clean_text(text)

    sender = await event.get_sender()

    await db.execute("""
    INSERT OR IGNORE INTO profiles (user_id, username, name)
    VALUES (?, ?, ?)
    """, (
        chat_id,
        getattr(sender, "username", "") or "",
        getattr(sender, "first_name", "") or "Unknown"
    ))
    await db.commit()

    async with db.execute(
        "SELECT language, lang_manual FROM profiles WHERE user_id=?",
        (chat_id,)
    ) as cur:
        row = await cur.fetchone()

    if not row:
        return  # на всякий

    lang, manual = row

    if not lang and manual == 0:
        detected = detect_language(text)

        if detected in ("ru", "en"):
            await set_user_language(chat_id, detected)
            lang = detected

    if event.message.voice:
        try:
            voice_bot = "@my_voice_messages_bot"
            async with client.conversation(voice_bot, timeout=30) as conv:
                await event.message.forward_to(voice_bot)
                response = await conv.get_response()
                if response and response.text:
                    text = f"[Голосовое]: {response.text}"
                else:
                    text = "[Голосовое сообщение]"
        except Exception as e:
            print(f"Ошибка расшифровки: {e}")
            text = "[Голосовое сообщение]"

    await db.execute(
        "INSERT INTO messages (chat_id, sender_id, text) VALUES (?, ?, ?)",
        (chat_id, chat_id, text)
    )
    await db.commit()

    keywords = ["люблю", "нравится", "занимаюсь", "увлекаюсь"]

    if any(k in text.lower() for k in keywords):
        new_hobbies = await extract_hobbies(text)

        if new_hobbies:
            # получаем старые
            async with db.execute(
                "SELECT hobbies FROM profiles WHERE user_id=?",
                (chat_id,)
            ) as cur:
                row = await cur.fetchone()

            old_hobbies = []
            if row and row[0]:
                old_hobbies = [h.strip().lower() for h in row[0].split(",")]

            combined = list(set(old_hobbies + new_hobbies))

            hobbies_str = ", ".join(combined)

            await db.execute(
                "UPDATE profiles SET hobbies=? WHERE user_id=?",
                (hobbies_str, chat_id)
            )
            await db.commit()

    if chat_id in pending_tasks:
        pending_tasks[chat_id].cancel()

    async def delayed_response(mode, lang):
        try:
            await asyncio.sleep(15)

            async with db.execute(
                "SELECT status, hobbies FROM profiles WHERE user_id=?",
                (chat_id,)
            ) as cur:
                row = await cur.fetchone()
                if not row:
                    return
                status, hobbies = row

            if status != 'active':
                return

            async with db.execute(
                "SELECT text, sender_id FROM messages WHERE chat_id=? ORDER BY timestamp DESC LIMIT 10",
                (chat_id,)
            ) as cur:
                rows = await cur.fetchall()

            history = "\n".join([
                f"{'Я' if r[1] != chat_id else 'Собеседник'}: {r[0]}"
                for r in reversed(rows)
            ])

            hobbies_context = f"\nХобби собеседника: {hobbies}" if hobbies else ""
            prompt_type = conf["PROMPT_INTRO"] if mode == 0 else conf["PROMPT_CHAT"]

            if not lang:
                lang = "ru"

            full_prompt = (
                f"{conf['MY_BIO']}\n"
                f"{hobbies_context}\n"
                f"{prompt_type}\n"
                f"Language: {lang}\n"
                f"Respond ONLY in {lang}. Do NOT translate.\n"
                f"История диалога:\n{history}\n"
                f"Напиши ответ:"
            )

            reply_text = await call_groq_api(full_prompt)

            parts = split_sentences(reply_text)

            for part in parts:
                await client.send_message(chat_id, part)

            await db.execute(
                "INSERT INTO messages (chat_id, sender_id, text) VALUES (?, ?, ?)",
                (chat_id, 0, reply_text)
            )
            await db.commit()

        except asyncio.CancelledError:
            pass

        except Exception as e:
            signals.error_signal.emit("ERR_RESPONSE_FAIL")

    async def get_mode():
        async with db.execute(
            "SELECT bot_mode FROM profiles WHERE user_id=?",
            (chat_id,)
        ) as cur:
            row = await cur.fetchone()
            return row[0] if row else 0

    mode = await get_mode()

    task = asyncio.create_task(delayed_response(mode, lang))
    pending_tasks[chat_id] = task


class BotSignals(QObject):
    status_changed = pyqtSignal(bool)
    chat_list_updated = pyqtSignal()
    data_loaded = pyqtSignal(list)
    update_summary_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)

signals = BotSignals()

async def init_db():
    database = await aiosqlite.connect(DB_PATH)
    await database.execute("CREATE TABLE IF NOT EXISTS profiles (user_id INTEGER PRIMARY KEY, username TEXT, name TEXT, status TEXT DEFAULT 'active', is_me INTEGER DEFAULT 0, bot_mode INTEGER DEFAULT 0, hobbies TEXT DEFAULT '')")
    try:
        await database.execute("ALTER TABLE profiles ADD COLUMN language TEXT")
    except:
        pass
    await database.execute("CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER, sender_id INTEGER, text TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)")
    try:
        await database.execute("ALTER TABLE profiles ADD COLUMN lang_manual INTEGER DEFAULT 0")
    except:
        pass
    await database.commit()
    return database

class RestrictedScrollArea(QScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_scroll_allowed = False

    def wheelEvent(self, event):
        if self.is_scroll_allowed:
            super().wheelEvent(event)
        else:
            event.ignore()

class ChatItem(QFrame):

    def __init__(self, user_id, name, status, bot_mode=0, is_add_button=False, parent_app=None):
        super().__init__()
        self.setMaximumWidth(340)
        self.user_id = user_id
        self.name = name if len(name) <= 10 else name[:10] + "..."
        self.bot_status = status
        self.bot_mode = bot_mode
        self.is_add_button = is_add_button
        self.parent_app = parent_app
        self.initUI()

    def initUI(self):
        self.setFixedHeight(70) 
        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 5, 15, 5)
        layout.setSpacing(10)

        self.avatar = QLabel()
        self.avatar.setFixedSize(48, 48)
        self.avatar.setScaledContents(True)
        
        if self.is_add_button:
            self.avatar.setStyleSheet("background-color: white; border-radius: 24px; color: #3040b0; font-size: 24px; font-weight: bold;")
            self.avatar.setText("+")
            self.avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        else:
            self.avatar.setStyleSheet("background-color: transparent; border-radius: 24px;")
            if os.path.exists(IMAGE_PATH):
                pixmap = QPixmap(IMAGE_PATH)
                self.avatar.setPixmap(pixmap.scaled(48, 48, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation))
            
        layout.addWidget(self.avatar)

        self.name_lbl = QLabel(self.name)
        self.name_lbl.setStyleSheet("color: white; font-size: 15px; font-weight: 500;")
        layout.addWidget(self.name_lbl)
        
        if not self.is_add_button:
            self.lan_btn = QPushButton("LAN")
            self.lan_btn.clicked.connect(self.toggle_language)
            self.lan_btn.setFixedSize(40, 28)
            self.lan_btn.setStyleSheet(f"""
                background-color: {"#3f51b5" if self.bot_mode == 0 else "#9c27b0"};
                color: white;
                border-radius: 14px;
                font-weight: bold;
                border: none;
            """)
            async def get_lang():
                async with db.execute(
                    "SELECT language FROM profiles WHERE user_id=?",
                    (self.user_id,)
                ) as cur:
                    row = await cur.fetchone()
                    return row[0] if row else None

            def set_lang_text(lang):
                if lang == "ru":
                    self.lan_btn.setText("RU")
                elif lang == "en":
                    self.lan_btn.setText("EN")
                else:
                    self.lan_btn.setText("LAN")

            async def init_lang():
                lang = await get_lang()
                set_lang_text(lang)

            asyncio.run_coroutine_threadsafe(init_lang(), loop)

        layout.addSpacing(0)

        btn_container = QHBoxLayout()
        btn_container.setSpacing(4)

        if not self.is_add_button:
            self.mode_btn = QPushButton("1" if self.bot_mode == 0 else "2")
            self.mode_btn.setFixedSize(35, 28)
            mode_color = "#3f51b5" if self.bot_mode == 0 else "#9c27b0"
            self.mode_btn.setStyleSheet(f"background-color: {mode_color}; color: white; border-radius: 14px; font-weight: bold; border: none;")
            self.mode_btn.clicked.connect(self.toggle_mode)

            self.btn = QPushButton("ON" if self.bot_status == 'active' else "OFF")
            self.btn.setFixedSize(55, 28)
            btn_color = "#ff9800" if self.bot_status == 'active' else "#555555"
            self.btn.setStyleSheet(f"background-color: {btn_color}; color: white; border-radius: 14px; font-weight: bold; border: none;")
            self.btn.clicked.connect(self.toggle_status)

            self.more_btn = QPushButton("⋮")
            self.more_btn.setFixedSize(30, 30)
            self.more_btn.setStyleSheet("color: white; border: none; font-size: 20px; font-weight: bold;")
            self.more_btn.clicked.connect(lambda: self.parent_app.open_chat_menu(self.user_id))

            btn_container.addWidget(self.lan_btn)
            btn_container.addWidget(self.mode_btn)
            btn_container.addWidget(self.btn)
            btn_container.addWidget(self.more_btn)

        layout.addLayout(btn_container)
        
        self.setStyleSheet("background: transparent;")

    def toggle_language(self):
    
        async def update():
            async with db.execute(
                "SELECT language FROM profiles WHERE user_id=?",
                (self.user_id,)
            ) as cur:
                row = await cur.fetchone()
                current = row[0] if row and row[0] else None

            # логика переключения
            if current == "ru":
                new_lang = "en"
            else:
                new_lang = "ru"

            await db.execute(
                "UPDATE profiles SET language=?, lang_manual=1 WHERE user_id=?",
                (new_lang, self.user_id)
            )
            await db.commit()

            return new_lang

        future = asyncio.run_coroutine_threadsafe(update(), loop)
        future.add_done_callback(done)

        def done(f):
            new_lang = f.result()
            QTimer.singleShot(0, lambda: self.lan_btn.setText(new_lang.upper()))

    def toggle_mode(self):
        new_mode = 1 if self.bot_mode == 0 else 0
        self.bot_mode = new_mode  # ← ВАЖНО

        # сразу обновляем UI
        self.mode_btn.setText("1" if new_mode == 0 else "2")
        mode_color = "#3f51b5" if new_mode == 0 else "#9c27b0"
        self.mode_btn.setStyleSheet(
            f"background-color: {mode_color}; color: white; border-radius: 14px; font-weight: bold; border: none;"
        )

        async def update():
            await db.execute(
                "UPDATE profiles SET bot_mode=? WHERE user_id=?",
                (new_mode, self.user_id)
            )
            await db.commit()

        asyncio.run_coroutine_threadsafe(update(), loop)

    def toggle_status(self):
        new_status = 'paused' if self.bot_status == 'active' else 'active'
        async def update():
            await db.execute("UPDATE profiles SET status=? WHERE user_id=?", (new_status, self.user_id))
            await db.commit()
            signals.chat_list_updated.emit()
        asyncio.run_coroutine_threadsafe(update(), loop)

    def mousePressEvent(self, event):
        if self.is_add_button and self.parent_app:
            self.parent_app.add_chat_dialog()
        super().mousePressEvent(event)

class MainApp(QWidget):

    def show_error(self, text):
        self.error_label.setText(text)

        self.error_label.setGeometry(30, -60, 300, 45)
        self.error_label.show()

        self.anim_err = QPropertyAnimation(self.error_label, b"pos")
        self.anim_err.setDuration(250)
        self.anim_err.setStartValue(QPoint(30, -60))
        self.anim_err.setEndValue(QPoint(30, 20))
        self.anim_err.start()

        QTimer.singleShot(3000, self.hide_error)


    def hide_error(self):
        self.anim_err = QPropertyAnimation(self.error_label, b"pos")
        self.anim_err.setDuration(250)
        self.anim_err.setStartValue(self.error_label.pos())
        self.anim_err.setEndValue(QPoint(30, -60))
        self.anim_err.finished.connect(self.error_label.hide)
        self.anim_err.start()
        
    def __init__(self):
        super().__init__()
        self.is_running = False
        self.panel_expanded = False
        self.drag_start_y = 0
        self.active_chat_id = None
        self.initUI()
        
        signals.chat_list_updated.connect(self.refresh_chats)
        signals.data_loaded.connect(self.render_chat_list)
        signals.status_changed.connect(self.update_bot_status_ui)
        signals.update_summary_signal.connect(self.set_summary_text_safe)
        signals.error_signal.connect(self.show_error)
        
        QTimer.singleShot(500, self.refresh_chats)

    def animate_button_click(self, button):
        original_style = button.styleSheet()

        darker_style = original_style.replace("#ff9800", "#cc7a00")

        button.setStyleSheet(darker_style)

        QTimer.singleShot(200, lambda: button.setStyleSheet(original_style))

    def clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)

            if item.widget():
                item.widget().deleteLater()

            elif item.layout():
                self.clear_layout(item.layout())

    def initUI(self):
        self.setFixedSize(360, 640)
        self.setWindowTitle("FiaskoAI") 
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self.main_frame = QFrame(self)
        self.main_frame.setGeometry(0, 0, 360, 640)
        self.main_frame.setStyleSheet("background-color: #1a1a1a; border-radius: 0px;")

        self.close_btn = QPushButton("✕", self.main_frame)
        self.close_btn.setGeometry(20, 20, 30, 30)
        self.close_btn.setStyleSheet("color: #ff9800; border: none; font-size: 18px;")
        self.close_btn.clicked.connect(self.close)

        self.settings_btn = QPushButton("⚙", self.main_frame)
        self.settings_btn.setGeometry(310, 20, 30, 30)
        self.settings_btn.setStyleSheet("color: white; border: none; font-size: 20px;")
        self.settings_btn.clicked.connect(self.open_settings)

        self.title = QLabel("FiaskoAI", self.main_frame)
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title.setGeometry(0, 70, 360, 40)
        self.title.setStyleSheet("color: white; font-size: 32px; font-weight: bold;")

        self.status_lbl = QLabel("offline", self.main_frame)
        self.status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_lbl.setGeometry(0, 110, 360, 20)
        self.status_lbl.setStyleSheet("color: #4158D0; font-size: 18px; font-weight: bold;")

        self.conn_btn = QPushButton("Connect", self.main_frame)
        self.conn_btn.setGeometry(80, 180, 200, 60)
        self.conn_btn.setStyleSheet("background-color: #3f51b5; color: white; border-radius: 20px; font-size: 20px; font-weight: bold;")
        self.conn_btn.clicked.connect(self.toggle_bot)

        self.chat_panel = QFrame(self.main_frame)
        self.panel_min_y = 280
        self.panel_max_y = 80
        self.chat_panel.setGeometry(0, self.panel_min_y, 360, 640 - self.panel_min_y)
        self.chat_panel.setStyleSheet("background-color: #3040b0; border-top-left-radius: 40px; border-top-right-radius: 40px;")
        
        self.handle = QFrame(self.chat_panel)
        self.handle.setGeometry(150, 15, 60, 5)
        self.handle.setStyleSheet("background-color: #5c6bc0; border-radius: 2px;")
        
        lbl_chats = QLabel("Chats", self.chat_panel)
        lbl_chats.setGeometry(30, 30, 100, 30)
        lbl_chats.setStyleSheet("color: white; font-size: 18px; font-weight: bold;")

        self.scroll = RestrictedScrollArea(self.chat_panel)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setGeometry(0, 70, 360, 280)
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("border: none; background: transparent;")
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        self.scroll_content = QWidget()
        self.chat_layout = QVBoxLayout(self.scroll_content)
        self.chat_layout.setContentsMargins(0, 0, 0, 20)
        self.chat_layout.setSpacing(2)
        self.scroll.setWidget(self.scroll_content)

        self.chat_panel.mousePressEvent = self.panel_press
        self.chat_panel.mouseMoveEvent = self.panel_move

        self.overlay = QFrame(self.main_frame)
        self.overlay.setGeometry(0, 640, 360, 640)
        self.overlay.setStyleSheet("background-color: #1a1a1a; border-radius: 0px;")
        self.overlay_layout = QVBoxLayout(self.overlay)
        self.overlay_layout.setContentsMargins(20, 30, 20, 20)
        self.overlay.hide()

        self.side_menu = QFrame(self.main_frame)
        self.side_menu.setGeometry(360, 0, 360, 640)
        self.side_menu.setStyleSheet("background-color: #1a1a1a; border-left: 2px solid #3040b0;")
        self.side_menu_layout = QVBoxLayout(self.side_menu)
        self.side_menu_layout.setContentsMargins(15, 60, 15, 20)
        self.side_menu_layout.setSpacing(15)
        self.side_menu.hide()

        self.error_label = QLabel(self.main_frame)
        self.error_label.setGeometry(40, 20, 280, 40) 
        self.error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.error_label.setStyleSheet("""
            background-color: white;
            color: black;
            border-radius: 12px;
            font-size: 14px;
            font-weight: bold;
        """)

        self.error_label.hide()

    def switch_language(self, chat_id):
        async def update():
            async with db.execute(
                "SELECT language FROM profiles WHERE user_id=?",
                (chat_id,)
            ) as cur:
                row = await cur.fetchone()
                current = row[0] if row and row[0] else None

            new_lang = "en" if current == "ru" else "ru"

            await db.execute(
                "UPDATE profiles SET language=? WHERE user_id=?",
                (new_lang, chat_id)
            )
            await db.commit()

            return new_lang

        future = asyncio.run_coroutine_threadsafe(update(), loop)

        def done_callback(f):
            new_lang = f.result()
            self.lan_btn.setText(new_lang.upper())

        future.add_done_callback(done_callback)

    def set_summary_text_safe(self, text):
        self.summary_text.setText(text)

    def animate_panel(self, target_y):
        target_h = 640 - target_y
        self.anim = QPropertyAnimation(self.chat_panel, b"geometry")
        self.anim.setDuration(400)
        self.anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.anim.setStartValue(self.chat_panel.geometry())
        self.anim.setEndValue(QRect(0, int(target_y), 360, int(target_h)))
        self.scroll.is_scroll_allowed = (target_y == self.panel_max_y)
        self.anim.start()
        self.scroll.setFixedHeight(int(target_h) - 80)

    def show_overlay(self, height_ratio=1.0):
        self.overlay.show()
        self.overlay.raise_()
        target_y = 640 * (1 - height_ratio)
        self.anim_ov = QPropertyAnimation(self.overlay, b"geometry")
        self.anim_ov.setDuration(300)
        self.anim_ov.setStartValue(QRect(0, 640, 360, 640))
        self.anim_ov.setEndValue(QRect(0, int(target_y), 360, 640))
        self.anim_ov.start()

    def hide_overlay(self):
        self.anim_ov = QPropertyAnimation(self.overlay, b"geometry")
        self.anim_ov.setDuration(300)
        self.anim_ov.setStartValue(self.overlay.geometry())
        self.anim_ov.setEndValue(QRect(0, 640, 360, 640))
        self.anim_ov.finished.connect(self.overlay.hide)
        self.anim_ov.start()

    def open_chat_menu(self, user_id):
        self.active_chat_id = user_id
        self.clear_layout(self.side_menu_layout)

        del_btn = QPushButton("Delete chat")
        del_btn.setFixedHeight(50)
        del_btn.setStyleSheet("background-color: #ff4444; color: white; border-radius: 15px; font-weight: bold; font-size: 16px;")
        del_btn.clicked.connect(self.action_delete_chat)
        self.side_menu_layout.addWidget(del_btn)

        write_btn = QPushButton("Write First")
        write_btn.setFixedHeight(50)
        write_btn.setStyleSheet("background-color: #ff9800; color: white; border-radius: 15px; font-weight: bold; font-size: 16px;")
        write_btn.clicked.connect(lambda: (
            self.animate_button_click(write_btn),
            self.action_write_first()
        ))
        self.side_menu_layout.addWidget(write_btn)

        sync_btn = QPushButton("Sync chat")
        sync_btn.setFixedHeight(50)
        sync_btn.setStyleSheet("background-color: #ff9800; color: white; border-radius: 15px; font-weight: bold; font-size: 16px;")
        sync_btn.clicked.connect(lambda: (
            self.animate_button_click(sync_btn),
            self.action_sync_chat()
        ))
        self.side_menu_layout.addWidget(sync_btn)

        sum_btn = QPushButton("Summary")
        sum_btn.setFixedHeight(50)
        sum_btn.setStyleSheet("background-color: #ff9800; color: white; border-radius: 15px; font-weight: bold; font-size: 16px;")
        self.side_menu_layout.addWidget(sum_btn)

        self.date_input = QLineEdit()
        self.date_input.setPlaceholderText("DDMM")
        self.date_input.setFixedHeight(40)
        self.date_input.setStyleSheet("background: #333; color: white; padding: 5px; border-radius: 10px; font-size: 14px;")
        self.side_menu_layout.addWidget(self.date_input)

        self.summary_text = QTextEdit()
        self.summary_text.setReadOnly(True)
        self.summary_text.setPlaceholderText("A retelling will appear here...")
        self.summary_text.setStyleSheet("background: #222; color: #ccc; border-radius: 10px; border: none; font-size: 13px;")
        self.side_menu_layout.addWidget(self.summary_text)

        sum_btn.clicked.connect(lambda: (
            self.animate_button_click(sum_btn),
            self.action_get_summary()
        ))

        back_btn = QPushButton("← Back")
        back_btn.setStyleSheet("color: #ff9800; border: none; font-size: 16px; margin-top: 10px;")
        back_btn.clicked.connect(self.hide_side_menu)
        self.side_menu_layout.addWidget(back_btn)

        self.side_menu.show()
        self.side_menu.raise_()
        self.anim_side = QPropertyAnimation(self.side_menu, b"pos")
        self.anim_side.setDuration(300)
        self.anim_side.setStartValue(QPoint(360, 0))
        self.anim_side.setEndValue(QPoint(0, 0))
        self.anim_side.start()

    def hide_side_menu(self):
        self.anim_side = QPropertyAnimation(self.side_menu, b"pos")
        self.anim_side.setDuration(300)
        self.anim_side.setStartValue(QPoint(0, 0))
        self.anim_side.setEndValue(QPoint(360, 0))
        self.anim_side.finished.connect(self.side_menu.hide)
        self.anim_side.start()

    def action_write_first(self):
        if not self.is_running or not client: return
        async def run():
            try:
                async with db.execute(
                    "SELECT bot_mode FROM profiles WHERE user_id=?",
                    (self.active_chat_id,)
                ) as cur:
                    row = await cur.fetchone()
                    mode = row[0] if row else 0

                print(f"[WRITE_FIRST DEBUG] mode={mode}")

                prompt_type = conf["PROMPT_INTRO"] if mode == 0 else conf["PROMPT_CHAT"]

                prompt = f"{conf['MY_BIO']}\n{prompt_type}\nНапиши первое сообщение для начала диалога."

                text = await call_groq_api(prompt)

                await client.send_message(self.active_chat_id, text)

                signals.update_summary_signal.emit("Сообщение отправлено!")

            except Exception as e:
                signals.update_summary_signal.emit(f"Error: {e}")
        asyncio.run_coroutine_threadsafe(run(), loop)

    def action_delete_chat(self):
    
        self.hide_side_menu()

        async def run():
            await db.execute("DELETE FROM profiles WHERE user_id=?", (self.active_chat_id,))
            await db.execute("DELETE FROM messages WHERE chat_id=?", (self.active_chat_id,))
            await db.commit()
            signals.chat_list_updated.emit()

        asyncio.run_coroutine_threadsafe(run(), loop)

    def action_sync_chat(self):
        if not self.is_running: return
        async def run():
            try:
                entity = await client.get_entity(self.active_chat_id)
                async for msg in client.iter_messages(entity, limit=100):
                    if msg.text:
                        await db.execute("INSERT OR IGNORE INTO messages (chat_id, sender_id, text, timestamp) VALUES (?, ?, ?, ?)",
                                         (self.active_chat_id, msg.sender_id, msg.text, msg.date))
                await db.commit()
                signals.update_summary_signal.emit("Sync complete.")
            except Exception as e:
                signals.update_summary_signal.emit(f"Error: {e}")
        asyncio.run_coroutine_threadsafe(run(), loop)

    def action_get_summary(self):
        date_str = self.date_input.text()
        if len(date_str) != 4: return
        
        signals.update_summary_signal.emit("Retelling generation...")
        
        async def run():
            try:
                day = date_str[:2]
                month = date_str[2:]
                target = f"{datetime.now().year}-{month}-{day}%"
                async with db.execute("SELECT text FROM messages WHERE chat_id=? AND timestamp LIKE ? LIMIT 100", (self.active_chat_id, target)) as cur:
                    rows = await cur.fetchall()
                    history = "\n".join([r[0] for r in rows if r[0]])
                    if not history:
                        signals.update_summary_signal.emit("No messages were found on this date.")
                        return
                    
                    ai_summary = await generate_ai_summary(history)
                    header = f"Summary for {day}.{month} ({len(rows)} msgs):\n\n"
                    signals.update_summary_signal.emit(header + ai_summary)
            except Exception as e:
                signals.update_summary_signal.emit(f"Error: {str(e)}")
        asyncio.run_coroutine_threadsafe(run(), loop)

    def open_settings(self):
        global conf
        self.clear_layout(self.overlay_layout)

        title = QLabel("Settings")
        title.setStyleSheet("color: #ff9800; font-size: 22px; font-weight: bold; margin-bottom: 10px;")
        self.overlay_layout.setContentsMargins(20, 40, 20, 20)
        self.overlay_layout.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none; background: transparent;")
        content = QWidget()
        layout = QVBoxLayout(content)

        layout.addWidget(QLabel("API ID:"))
        api_id_input = QLineEdit(str(conf["API_ID"]))
        api_id_input.setStyleSheet("background: #333; color: white; padding: 5px; border-radius: 5px;")
        layout.addWidget(api_id_input)

        layout.addWidget(QLabel("API HASH:"))
        api_hash_input = QLineEdit(conf["API_HASH"])
        api_hash_input.setStyleSheet("background: #333; color: white; padding: 5px; border-radius: 5px;")
        layout.addWidget(api_hash_input)

        layout.addWidget(QLabel("Groq API Key:"))
        key_input = QLineEdit(conf["API_KEY"])
        key_input.setStyleSheet("background: #333; color: white; padding: 5px; border-radius: 5px;")
        layout.addWidget(key_input)

        layout.addWidget(QLabel("Description of you (hobby, having a dog/car):"))
        bio_input = QTextEdit(conf["MY_BIO"])
        bio_input.setFixedHeight(50)
        bio_input.setStyleSheet("background: #333; color: white; border-radius: 5px;")
        layout.addWidget(bio_input)

        layout.addWidget(QLabel("Prompt 1:"))
        p_intro = QTextEdit(conf.get("PROMPT_INTRO", ""))
        p_intro.setFixedHeight(40)
        p_intro.setStyleSheet("background: #333; color: white; border-radius: 5px;")
        layout.addWidget(p_intro)

        layout.addWidget(QLabel("Prompt 2:"))
        p_chat = QTextEdit(conf.get("PROMPT_CHAT", ""))
        p_chat.setFixedHeight(40)
        p_chat.setStyleSheet("background: #333; color: white; border-radius: 5px;")
        layout.addWidget(p_chat)

        scroll.setWidget(content)
        self.overlay_layout.addWidget(scroll)

        btn_box = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.setStyleSheet("background: #ff9800; color: white; font-weight: bold; padding: 10px; border-radius: 10px;")
        back_btn = QPushButton("Back")
        back_btn.setStyleSheet("background: #555; color: white; font-weight: bold; padding: 10px; border-radius: 10px;")
        btn_box.addWidget(back_btn)
        btn_box.addWidget(save_btn)
        self.overlay_layout.addLayout(btn_box)

        def do_save():
            global conf
            try:
                conf["API_ID"] = int(api_id_input.text())
                conf["API_HASH"] = api_hash_input.text().strip()
                conf["API_KEY"] = key_input.text().strip()
                conf["MY_BIO"] = bio_input.toPlainText()
                conf["PROMPT_INTRO"] = p_intro.toPlainText()
                conf["PROMPT_CHAT"] = p_chat.toPlainText()
                save_config(conf)
                self.hide_overlay()
            except: pass
        
        save_btn.clicked.connect(do_save)
        back_btn.clicked.connect(self.hide_overlay)
        self.show_overlay(height_ratio=1.0)

    def add_chat_dialog(self):
        self.clear_layout(self.overlay_layout)

        self.overlay_layout.setContentsMargins(20, 20, 20, 20)
        
        title = QLabel("Add Chat")
        title.setStyleSheet("color: #ff9800; font-size: 20px; font-weight: bold; margin-bottom: 5px;")
        self.overlay_layout.addWidget(title)

        inpt = QLineEdit()
        inpt.setPlaceholderText("Username (without @)")
        inpt.setStyleSheet("background: #333; color: white; padding: 10px; border-radius: 10px; font-size: 15px;")
        self.overlay_layout.addWidget(inpt)
        
        btn_box = QHBoxLayout()
        btn = QPushButton("Add")
        btn.setStyleSheet("background: #ff9800; color: white; font-weight: bold; padding: 10px; border-radius: 10px;")
        back_btn = QPushButton("Back")
        back_btn.setStyleSheet("background: #555; color: white; font-weight: bold; padding: 10px; border-radius: 10px;")
        btn_box.addWidget(back_btn)
        btn_box.addWidget(btn)
        self.overlay_layout.addLayout(btn_box)
        
        self.overlay_layout.addStretch()

        async def add():
            try:
                un = inpt.text().replace("@", "").strip()
                if not un:
                    return

                u = await client.get_entity(un)

                await db.execute("""
                    INSERT OR IGNORE INTO profiles (user_id, username, name, status, is_me)
                    VALUES (?, ?, ?, 'active', 0)
                """, (
                    u.id,
                    getattr(u, "username", "") or "",
                    getattr(u, "first_name", "") or "Unknown"
                ))

                await db.commit()

                signals.chat_list_updated.emit()
                self.hide_overlay()

            except Exception as e:
                print("ADD CHAT ERROR:", e)

        btn.clicked.connect(lambda: asyncio.run_coroutine_threadsafe(add(), loop))
        back_btn.clicked.connect(self.hide_overlay)
        self.show_overlay(height_ratio=0.25)

    def refresh_chats(self):
        async def fetch():
            global db
            if not db: db = await init_db()
            async with db.execute("SELECT user_id, name, status, bot_mode FROM profiles WHERE is_me=0 ORDER BY user_id DESC") as cur:
                users = await cur.fetchall()
                signals.data_loaded.emit(users)
        asyncio.run_coroutine_threadsafe(fetch(), loop)

    def render_chat_list(self, users):
        self.clear_layout(self.chat_layout)  # ✅ правильный layout

        for u in users:
            self.chat_layout.addWidget(ChatItem(u[0], u[1], u[2], u[3], parent_app=self))
        
        add_item = ChatItem(0, "Add Chat", "", 0, is_add_button=True, parent_app=self)
        self.chat_layout.addWidget(add_item)
        self.chat_layout.addStretch()

    def panel_press(self, event): self.drag_start_y = event.globalPosition().y()
    def panel_move(self, event):
        delta = event.globalPosition().y() - self.drag_start_y
        if delta < -30 and not self.panel_expanded:
            self.animate_panel(self.panel_max_y); self.panel_expanded = True
        elif delta > 30 and self.panel_expanded:
            self.animate_panel(self.panel_min_y); self.panel_expanded = False

    def update_bot_status_ui(self, running):
        self.is_running = running
        self.status_lbl.setText("online" if running else "offline")
        self.status_lbl.setStyleSheet(f"color: {'#ff9800' if running else '#4158D0'}; font-size: 18px; font-weight: bold;")
        self.conn_btn.setText("Disconnect" if running else "Connect")
        if running: self.refresh_chats()

    def toggle_bot(self):
        original_style = self.conn_btn.styleSheet()
        self.conn_btn.setStyleSheet(original_style.replace("#3f51b5", "#2a3780"))
        QTimer.singleShot(500, lambda: self.conn_btn.setStyleSheet(original_style))
        if not self.is_running: asyncio.run_coroutine_threadsafe(start_client(), loop)
        else: asyncio.run_coroutine_threadsafe(stop_client(), loop)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton: self.window_drag_pos = event.globalPosition().toPoint()
    def mouseMoveEvent(self, event):
        if hasattr(self, 'window_drag_pos'):
            self.move(self.pos() + event.globalPosition().toPoint() - self.window_drag_pos)
            self.window_drag_pos = event.globalPosition().toPoint()

async def start_client():
    global client, db
    try:
        if not db:
            db = await init_db()

        if not client:
            client = TelegramClient("session", conf["API_ID"], conf["API_HASH"])

        await client.start()

        if not hasattr(client, "_handler_added"):
            client.add_event_handler(handle_new_message, events.NewMessage)
            client._handler_added = True

        signals.status_changed.emit(True)

    except TimeoutError:
        signals.error_signal.emit("ERR_TELEGRAM_TIMEOUT")

    except Exception as e:
        signals.error_signal.emit(f"ERR_CONNECT_FAIL")

async def stop_client():
    if client:
        
        client.remove_event_handler(handle_new_message, events.NewMessage)
        await client.disconnect()
    signals.status_changed.emit(False)

def run_asyncio_loop(loop_param):
    asyncio.set_event_loop(loop_param)
    loop_param.run_forever()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    loop = asyncio.new_event_loop()
    window = MainApp()
    window.show()
    threading.Thread(target=run_asyncio_loop, args=(loop,), daemon=True).start()
    sys.exit(app.exec())