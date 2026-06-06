import asyncio
import json
import os

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
        f"Проанализируй переписку и сделай краткий пересказ на языке переписки. "
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


async def transcribe_audio_file(file_path):
    global http_session
    
    selected_api = conf.get("SELECTED_API", "groq").strip().lower()
    actual_api_key = conf.get("API_KEY", "")
    
    if selected_api == "chatgpt":
        url = "https://api.openai.com/v1/audio/transcriptions"
        model = "whisper-1"
    else:
        url = "https://api.groq.com/openai/v1/audio/transcriptions"
        model = "whisper-large-v3"
        
    headers = {
        "Authorization": f"Bearer {actual_api_key}",
    }
    
    data = aiohttp.FormData()
    try:
        with open(file_path, 'rb') as f:
            file_bytes = f.read()
        data.add_field('file', file_bytes, filename=os.path.basename(file_path))
        data.add_field('model', model)
    except Exception as exc:
        print("Failed to read audio file for transcription:", exc)
        return ""
    
    try:
        async with http_session.post(url, headers=headers, data=data, timeout=30) as resp:
            if resp.status == 200:
                res_data = await resp.json()
                return res_data.get("text", "").strip()
            else:
                err_text = await resp.text()
                print(f"STT error {resp.status}: {err_text}")
                return ""
    except Exception as exc:
        print("STT Exception:", exc)
        return ""


async def describe_image_or_frames(images_b64, media_type):
    global http_session
    
    if not images_b64:
        return ""
        
    selected_api = conf.get("SELECTED_API", "groq").strip().lower()
    api_cfg = API_CONFIGS.get(selected_api, API_CONFIGS["groq"])
    
    url = api_cfg["url"]
    actual_api_key = conf.get("API_KEY", "")
    
    if selected_api == "groq" or selected_api == "llama":
        model = "llama-3.2-11b-vision-preview"
    else:
        model = api_cfg["model"]
        
    headers = {
        "Authorization": f"Bearer {actual_api_key}",
        "Content-Type": "application/json",
    }
    
    prompt_text = (
        "This is an image/frame from our Telegram chat. "
        "Describe briefly (in 1-2 short sentences) what is shown on this image "
        "(e.g., people, objects, emotions, environment) so that the chatbot can understand the context. "
        "Respond in Russian."
    )
    if media_type == "video" or media_type == "video_note":
        prompt_text = (
            "These are sequential frames from a video message. "
            "Briefly describe what is happening in the video (actions, scene, emotions). "
            "Respond in Russian, in 1-2 short sentences."
        )
        
    content = [{"type": "text", "text": prompt_text}]
    
    for img in images_b64:
        content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{img}"
            }
        })
        
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": content
            }
        ],
        "temperature": 0.7,
        "max_tokens": 150,
    }
    
    try:
        async with http_session.post(url, headers=headers, json=payload, timeout=40) as resp:
            if resp.status == 200:
                res_data = await resp.json()
                return res_data["choices"][0]["message"]["content"].strip()
            else:
                err_text = await resp.text()
                print(f"Vision API error {resp.status}: {err_text}")
                return ""
    except Exception as exc:
        print("Vision API Exception:", exc)
        return ""
