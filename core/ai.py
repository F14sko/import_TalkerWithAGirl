import asyncio
import json

import aiohttp

from core.config import conf
from ui.widgets import signals

http_session = None
groq_semaphore = asyncio.Semaphore(3)

API_CONFIGS = {
    "gemini": {
        "url": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
        "model": "gemini-1.5-flash",
        "err_prefix": "ERR_GEMINI",
    },
    "chatgpt": {
        "url": "https://api.openai.com/v1/chat/completions",
        "model": "gpt-4o-mini",
        "err_prefix": "ERR_CHATGPT",
    },
    "llama": {
        "url": "https://api.groq.com/openai/v1/chat/completions",
        "model": "llama-3.1-8b-instant",
        "err_prefix": "ERR_LLAMA",
    },
    "groq": {
        "url": "https://api.groq.com/openai/v1/chat/completions",
        "model": "mixtral-8x7b-32768",
        "err_prefix": "ERR_GROQ",
    },
}


async def call_groq_api(prompt):
    global http_session

    selected_api = conf.get("SELECTED_API", "groq").strip().lower()
    api_cfg = API_CONFIGS.get(selected_api, API_CONFIGS["groq"])

    url = api_cfg["url"]
    model = api_cfg["model"]
    err_prefix = api_cfg["err_prefix"]

    async with groq_semaphore:
        actual_api_key = conf.get("API_KEY", "")

        headers = {
            "Authorization": f"Bearer {actual_api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": "Ты отвечаешь как человек. Коротко, живо, без лишней пунктуации.",
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.9,
            "max_tokens": 150,
        }

        try:
            async with http_session.post(
                url,
                headers=headers,
                json=payload,
                timeout=40,
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data["choices"][0]["message"]["content"].strip()

                await resp.text()
                signals.error_signal.emit(f"{err_prefix}_{resp.status}")
                return None

        except Exception:
            signals.error_signal.emit(f"{err_prefix}_CONNECTION")
            return None


async def generate_ai_summary(text_history):
    prompt = (
        f"Проанализируй переписку и сделай краткий пересказ на русском. "
        f"Ключевые темы и итоги.\n\nПереписка:\n{text_history}"
    )
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
    except Exception:
        signals.error_signal.emit("ERR_JSON_PARSE")

    return []
