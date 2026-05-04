import json
import os
from telethon.sync import TelegramClient

CONFIG_FILE = "config.json"

DEFAULT_CONFIG = {
    "API_ID": 0,
    "API_HASH": "",
    "API_KEY": "",
    "MY_BIO": "",
    "PROMPT_INTRO": "",
    "PROMPT_CHAT": ""
}


def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {**DEFAULT_CONFIG, **data}
        except:
            return DEFAULT_CONFIG
    return DEFAULT_CONFIG


def save_config(config):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4, ensure_ascii=False)


def main():
    print("=== Telegram Login Setup ===")

    config = load_config()

    # Ввод API данных
    try:
        api_id = int(input("Введите API_ID: ").strip())
    except:
        print("API_ID должен быть числом")
        return

    api_hash = input("Введите API_HASH: ").strip()

    if not api_hash:
        print("API_HASH не может быть пустым")
        return

    # Сохраняем в config.json
    config["API_ID"] = api_id
    config["API_HASH"] = api_hash
    save_config(config)

    print("Данные сохранены в config.json")

    # Авторизация Telegram
    print("\n=== Авторизация Telegram ===")

    with TelegramClient("session", api_id, api_hash) as client:
        client.start()
        print("Успешно авторизован! session создан.")


if __name__ == "__main__":
    main()

