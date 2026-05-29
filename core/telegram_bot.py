import asyncio

import aiohttp
from telethon import TelegramClient, events

from core import ai as ai_module
from core import database
from core.config import SESSION_STEM, conf
from core.avatars import download_chat_avatar
from core.database import get_profile_bio_text, init_db, set_my_user_id
from core.utils import (
    filter_casual,
    filter_formal,
    remove_emojis,
    store_message_timestamp,
)
from core.ai import call_groq_api, extract_hobbies
from ui.widgets import signals

client = None
loop = None
pending_tasks = {}


async def typing_indicator(client_instance, chat_id, duration):
    try:
        start = asyncio.get_event_loop().time()
        while asyncio.get_event_loop().time() - start < duration:
            async with client_instance.action(chat_id, "typing"):
                await asyncio.sleep(4)
    except asyncio.CancelledError:
        pass


async def handle_new_message(event):
    if not event.is_private:
        return

    chat_id = event.chat_id

    if event.message.photo or event.message.video_note:
        try:
            await database.db.execute(
                "UPDATE profiles SET status='paused' WHERE user_id=?",
                (chat_id,),
            )
            await database.db.commit()

            sender = await event.get_sender()
            chat_name = (
                getattr(sender, "first_name", "")
                or getattr(sender, "username", "")
                or str(chat_id)
            )

            await client.send_message(
                "me",
                f"attention check the chat: {chat_name}",
            )

            signals.chat_list_updated.emit()

        except Exception:
            pass

        return

    async with database.db.execute(
        "SELECT status FROM profiles WHERE user_id=?",
        (chat_id,),
    ) as cur:
        row = await cur.fetchone()

    if not row:
        return

    if row[0] != "active":
        return

    text = event.message.text or ""
    sender = await event.get_sender()

    await database.db.execute(
        """
        INSERT OR IGNORE INTO profiles (user_id, username, name)
        VALUES (?, ?, ?)
        """,
        (
            chat_id,
            getattr(sender, "username", "") or "",
            getattr(sender, "first_name", "") or "Unknown",
        ),
    )
    await database.db.commit()

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
        except Exception:
            text = "[Голосовое сообщение]"

    await database.db.execute(
        "INSERT OR IGNORE INTO messages "
        "(chat_id, sender_id, text, timestamp, tg_msg_id) VALUES (?, ?, ?, ?, ?)",
        (
            chat_id,
            chat_id,
            text,
            store_message_timestamp(event.message.date),
            event.message.id,
        ),
    )
    await database.db.commit()

    keywords = ["люблю", "нравится", "занимаюсь", "увлекаюсь"]

    if any(k in text.lower() for k in keywords):
        new_hobbies = await extract_hobbies(text)

        if new_hobbies:
            async with database.db.execute(
                "SELECT hobbies FROM profiles WHERE user_id=?",
                (chat_id,),
            ) as cur:
                row = await cur.fetchone()

            old_hobbies = []
            if row and row[0]:
                old_hobbies = [h.strip().lower() for h in row[0].split(",")]

            combined = list(set(old_hobbies + new_hobbies))
            hobbies_str = ", ".join(combined)

            await database.db.execute(
                "UPDATE profiles SET hobbies=? WHERE user_id=?",
                (hobbies_str, chat_id),
            )
            await database.db.commit()

    if chat_id in pending_tasks:
        pending_tasks[chat_id].cancel()

    async def delayed_response(mode):
        typing_task = None

        try:
            async def typing_loop():
                while True:
                    try:
                        async with client.action(chat_id, "typing"):
                            await asyncio.sleep(4)
                    except Exception:
                        break

            typing_task = asyncio.create_task(typing_loop())

            await asyncio.sleep(min(15 + len(text) * 0.05, 40))

            async with database.db.execute(
                "SELECT status, hobbies FROM profiles WHERE user_id=?",
                (chat_id,),
            ) as cur:
                row = await cur.fetchone()
                if not row:
                    return
                status, hobbies = row

            if status != "active":
                return

            async with database.db.execute(
                "SELECT text, sender_id FROM messages WHERE chat_id=? "
                "ORDER BY timestamp DESC LIMIT 10",
                (chat_id,),
            ) as cur:
                rows = await cur.fetchall()

            history = "\n".join(
                [
                    f"{'Я' if r[1] != chat_id else 'Собеседник'}: {r[0]}"
                    for r in reversed(rows)
                ]
            )

            hobbies_context = f"\nХобби собеседника: {hobbies}" if hobbies else ""
            prompt_type = conf["PROMPT_INTRO"] if mode == 0 else conf["PROMPT_CHAT"]

            response_lang = conf.get("LANGUAGE", "ru")

            profile_bio = await get_profile_bio_text()
            full_prompt = (
                f"{profile_bio}\n"
                f"{hobbies_context}\n"
                f"{prompt_type}\n"
                f"Language: {response_lang}\n"
                f"Respond ONLY in {response_lang}. Do NOT translate.\n"
                f"История диалога:\n{history}\n"
                f"Напиши ответ:"
            )

            reply_text = await call_groq_api(full_prompt)

            if not reply_text:
                return

            if typing_task:
                typing_task.cancel()

            async with database.db.execute(
                "SELECT communication_style FROM profiles WHERE user_id=?",
                (chat_id,),
            ) as cur:
                row = await cur.fetchone()

            style = (row[0] if row and row[0] else "formal").strip().lower()

            if style == "formal":
                parts = filter_formal(reply_text)
            else:
                parts = filter_casual(reply_text)

            parts = [remove_emojis(p) for p in parts]
            parts = [p for p in parts if p.strip()]

            sent_ids = []
            for part in parts:
                typing_task = asyncio.create_task(
                    typing_indicator(client, chat_id, 10)
                )
                await asyncio.sleep(10)
                typing_task.cancel()
                sent = await client.send_message(chat_id, part)
                if sent:
                    sent_ids.append(sent.id)

            tg_msg_id = sent_ids[-1] if sent_ids else None
            await database.db.execute(
                "INSERT OR IGNORE INTO messages "
                "(chat_id, sender_id, text, timestamp, tg_msg_id) VALUES (?, ?, ?, ?, ?)",
                (
                    chat_id,
                    0,
                    reply_text,
                    store_message_timestamp(None),
                    tg_msg_id,
                ),
            )
            await database.db.commit()

        except asyncio.CancelledError:
            pass

        except Exception:
            signals.error_signal.emit("ERR_RESPONSE_FAIL")

        finally:
            if typing_task:
                typing_task.cancel()
            pending_tasks.pop(chat_id, None)

    async def get_mode():
        async with database.db.execute(
            "SELECT bot_mode FROM profiles WHERE user_id=?",
            (chat_id,),
        ) as cur:
            row = await cur.fetchone()
            return row[0] if row else 0

    mode = await get_mode()
    task = asyncio.create_task(delayed_response(mode))
    pending_tasks[chat_id] = task


async def start_client():
    global client

    try:
        if not database.db:
            database.db = await init_db()

        if not client:
            client = TelegramClient(
                SESSION_STEM,
                conf["API_ID"],
                conf["API_HASH"],
            )

        await client.start()
        client.parse_mode = None

        me = await client.get_me()
        set_my_user_id(me.id)
        await database.db.execute(
            """
            INSERT OR IGNORE INTO profiles
            (user_id, username, name, status, is_me, communication_style, bot_mode)
            VALUES (?, ?, ?, 'active', 1, 'formal', 0)
            """,
            (
                me.id,
                getattr(me, "username", "") or "",
                getattr(me, "first_name", "") or "Me",
            ),
        )
        await database.db.execute(
            """
            UPDATE profiles SET username=?, name=?, is_me=1, status='active'
            WHERE user_id=?
            """,
            (
                getattr(me, "username", "") or "",
                getattr(me, "first_name", "") or "Me",
                me.id,
            ),
        )
        await database.db.commit()
        try:
            await download_chat_avatar(me.id)
            signals.avatar_updated.emit(me.id)
        except Exception:
            pass

        if not ai_module.http_session:
            ai_module.http_session = aiohttp.ClientSession()

        if not hasattr(client, "_handler_added"):
            client.add_event_handler(handle_new_message, events.NewMessage)
            client._handler_added = True

        signals.status_changed.emit(True)

    except TimeoutError:
        signals.error_signal.emit("ERR_TELEGRAM_TIMEOUT")

    except Exception:
        signals.error_signal.emit("ERR_CONNECT_FAIL")


async def stop_client():
    global client

    if client:
        client.remove_event_handler(handle_new_message, events.NewMessage)
        await client.disconnect()

        if ai_module.http_session:
            await ai_module.http_session.close()
            ai_module.http_session = None

    signals.status_changed.emit(False)
