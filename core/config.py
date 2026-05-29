import json
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_FILE = PROJECT_ROOT / "config.json"
SESSION_FILE = PROJECT_ROOT / "session.session"
SESSION_STEM = str(PROJECT_ROOT / "session")
IMAGE_PATH = PROJECT_ROOT / "avatar" / "ava.png"

DEFAULT_CONFIG = {
    "API_ID": 0,
    "API_HASH": "",
    "API_KEY": "",
    "LANGUAGE": "en",
    "THEME": "dark",
    "TIMEZONE": 3,
    "MY_BIO": "",
    "SELECTED_API": "groq",
    "PROMPT_INTRO": "ты — остроумный, уверенный в себе парень. Твоя цель — завязать непринужденный диалог. Правила общения: Краткость: Пиши не более 1–2 предложений. Никаких длинных абзацев. Живой язык: Используй современную лексику, но без перебора. Никакой лести: Не делай банальных комплиментов внешности. Используй легкий «пэйсинг» (поддразнивание). Инициатива: Всегда заканчивай ответ коротким открытым вопросом или призывом к действию. Запреты: Не используй фразы «Как прошел твой день?», «Чем занимаешься?», эмодзи-роботов и официальный тон. Правила: Краткость (1-2 предл.), живой язык, никакой лести. Завершай вопросом. ",
    "PROMPT_CHAT": "Ты — парень, который уже нравится этой девушке. Общайся расслабленно, тепло, иногда подкалывай и заигрывай. Тон уверенный, но не пошлый. Пиши коротко, в стиле мессенджеров. Используй контекст ваших шуток из истории. Правила общения: Краткость: Пиши не более 1–2 предложений. Никаких длинных абзацев. Живой язык: Используй современную лексику, но без перебора. Никакой лести: Не делай банальных комплиментов внешности. Инициатива: Всегда заканчивай ответ коротким открытым вопросом или призывом к действию. Запреты: Не используй фразы «Как прошел твой день?», «Чем занимаешься?», эмодзи-роботов и официальный тон. Правила: Краткость (1-2 предл.), живой язык, никакой лести. Завершай вопросом. ",
}


def load_config():
    if not CONFIG_FILE.exists():
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        try:
            return {**DEFAULT_CONFIG, **json.load(f)}
        except Exception:
            return DEFAULT_CONFIG.copy()


def ensure_config():
    if not CONFIG_FILE.exists():
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_CONFIG, f, indent=4, ensure_ascii=False)


def save_config(new_conf):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(new_conf, f, indent=4, ensure_ascii=False)


def reload_config():
    data = load_config()
    conf.clear()
    conf.update(data)
    return conf


translations = {
    "en": {
        "connect": "Connect",
        "disconnect": "Disconnect",
        "add_chat": "Add Chat",
        "delete_chat": "Delete chat",
        "write_first": "Write First",
        "sync_chat": "Sync chat",
        "summary": "Summary",
        "summary_placeholder": "A retelling will appear here...",
        "retelling_generation": "Retelling generation...",
        "no_messages": "No messages were found on this date.",
        "summary_for": "Summary for",
        "message_sent": "Message sent!",
        "back": "Back",
        "add": "Add",
        "change_style": "Change communication style",
        "formal_style": "Formal",
        "casual_style": "Casual",
        "formal_desc": "With proper punctuation",
        "casual_desc": "Without punctuation",
        "save": "Save",
        "tab_chats": "Chats",
        "tab_settings": "Settings",
        "tab_profile": "Profile",
        "new_chat": "+ New chat",
        "profile_name": "Name",
        "profile_age": "Age",
        "profile_about": "About me",
        "select_avatar": "Select Avatar",
        "chat_messages": "Messages",
        "language": "Interface language",
        "connect_first": "Connect Telegram first",
        "chat_settings": "Chat settings",
        "back_to_messages": "Back to messages",
        "select_prompt": "Response prompt",
        "prompt_intro": "Prompt 1",
        "prompt_chat": "Prompt 2",
        "add_chat_hint": "Telegram @username",
        "lang_en": "English",
        "lang_ru": "Russian",
        "theme": "Interface theme",
        "theme_dark": "Dark theme",
        "theme_light": "Light theme",
        "timezone": "Timezone",
        "selected_api": "API Model",
    },
    "ru": {
        "connect": "Подключить",
        "disconnect": "Отключить",
        "add_chat": "Добавить",
        "delete_chat": "Удалить чат",
        "write_first": "Написать первым",
        "sync_chat": "Синхронизировать чат",
        "summary": "Пересказ",
        "summary_placeholder": "Здесь появится пересказ...",
        "retelling_generation": "Создание пересказа...",
        "no_messages": "На эту дату сообщений не найдено.",
        "summary_for": "Пересказ за",
        "message_sent": "Сообщение отправлено!",
        "back": "Назад",
        "add": "Добавить",
        "change_style": "Изменить стиль общения",
        "formal_style": "Формальное",
        "casual_style": "Разговорный",
        "formal_desc": "Со всеми знаками\nпрепинания",
        "casual_desc": "Без знаков препинания",
        "save": "Сохранить",
        "tab_chats": "Чаты",
        "tab_settings": "Настройки",
        "tab_profile": "Профиль",
        "new_chat": "+ Новый чат",
        "profile_name": "Имя",
        "profile_age": "Возраст",
        "profile_about": "Информация о себе",
        "select_avatar": "Выбрать аватарку",
        "chat_messages": "Сообщения",
        "language": "Язык интерфейса",
        "connect_first": "Сначала подключите Telegram",
        "chat_settings": "Настройки чата",
        "back_to_messages": "К сообщениям",
        "select_prompt": "Промпт для ответов",
        "prompt_intro": "Промпт 1",
        "prompt_chat": "Промпт 2",
        "add_chat_hint": "Telegram @username",
        "lang_en": "English",
        "lang_ru": "Русский",
        "theme": "Тема интерфейса",
        "theme_dark": "Тёмная тема",
        "theme_light": "Светлая тема",
        "timezone": "Часовой пояс",
        "selected_api": "Модель API",
    },
}


def language_label(code):
    key = "lang_ru" if code == "ru" else "lang_en"
    return tr(key)


def tr(key):
    lang = conf.get("LANGUAGE", "en")
    return translations.get(lang, translations["en"]).get(key, key)


ensure_config()
conf = load_config()
