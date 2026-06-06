import json
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_FILE = PROJECT_ROOT / "config.json"
SESSION_FILE = PROJECT_ROOT / "session.session"
SESSION_STEM = str(PROJECT_ROOT / "session")
IMAGE_PATH = PROJECT_ROOT / "avatar" / "ava.png"
MEDIA_DIR = PROJECT_ROOT / "media"
MEDIA_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_CONFIG = {
    "API_ID": 0,
    "API_HASH": "",
    "API_KEY": "",
    "LANGUAGE": "en",
    "THEME": "dark",
    "TIMEZONE": 3,
    "MY_BIO": "",
    "SELECTED_API": "groq",
    "PROMPTS": {},
    "EXPERIMENTAL_MEDIA_REPLY": False,
}


def load_config():
    if not CONFIG_FILE.exists():
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
            if "PROMPTS" not in data:
                data["PROMPTS"] = {}
                if "PROMPT_INTRO" in data:
                    data["PROMPTS"]["Промпт 1"] = data["PROMPT_INTRO"]
                if "PROMPT_CHAT" in data:
                    data["PROMPTS"]["Промпт 2"] = data["PROMPT_CHAT"]
            return {**DEFAULT_CONFIG, **data}
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
        "add_chat_hint": "Telegram @username or ID",
        "add_chat_placeholder": "@username or ID",
        "settings_general": "General",
        "settings_prompts": "Prompts",
        "add_prompt_title": "Add Prompt",
        "prompt_name_label": "Prompt Name:",
        "prompt_name_placeholder": "e.g., Greeting",
        "prompt_text_label": "Prompt Text:",
        "prompt_text_placeholder": "Write your prompt here...",
        "error_no_prompts": "Please create prompts first!",
        "select_prompt": "Select prompt",
        "lang_en": "English",
        "lang_ru": "Russian",
        "theme": "Interface theme",
        "theme_dark": "Dark theme",
        "theme_light": "Light theme",
        "timezone": "Timezone",
        "selected_api": "API Model",
        "media_reply": "Media Reply (Experimental)",
        "media_reply_tooltip": "When the feature is disabled, voice messages, photos, and video notes pause the chat and send an error notification to Saved Messages. When the feature is enabled, it continues to work, sending everything to the AI (use at your own risk).",
        "media_reply_on": "Enabled",
        "media_reply_off": "Disabled",
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
        "add_chat_hint": "Telegram @username или ID",
        "add_chat_placeholder": "@username или ID",
        "settings_general": "Основные",
        "settings_prompts": "Промты",
        "add_prompt_title": "Добавить промпт",
        "prompt_name_label": "Название промпта:",
        "prompt_name_placeholder": "Например, Приветствие",
        "prompt_text_label": "Текст промпта:",
        "prompt_text_placeholder": "Напишите ваш промпт здесь...",
        "error_no_prompts": "Сначала создайте хотя бы один промпт!",
        "select_prompt": "Выберите промпт",
        "lang_en": "English",
        "lang_ru": "Русский",
        "theme": "Тема интерфейса",
        "theme_dark": "Тёмная тема",
        "theme_light": "Светлая тема",
        "timezone": "Часовой пояс",
        "selected_api": "Модель API",
        "media_reply": "Ответ на медиа (Экспериментально)",
        "media_reply_tooltip": "Когда функция выключена голосовые сообщения фото и кругляшки приостанавливают чат и отправляют уведомление об ошибке в избранное. При включении функции он продолжает работу, отправляя все ИИ (используйте на свой страх и риск)",
        "media_reply_on": "Включено",
        "media_reply_off": "Выключено",
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
