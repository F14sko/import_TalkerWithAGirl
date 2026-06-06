import aiosqlite

from core.config import PROJECT_ROOT

DB_PATH = str(PROJECT_ROOT / "dating_bot.db")
db = None
_my_user_id = None


def set_my_user_id(user_id):
    global _my_user_id
    _my_user_id = user_id


def get_my_user_id():
    return _my_user_id


async def resolve_my_user_id():
    global _my_user_id
    if _my_user_id is not None:
        return _my_user_id
    if not db:
        return None
    async with db.execute(
        "SELECT user_id FROM profiles WHERE is_me=1 LIMIT 1"
    ) as cur:
        row = await cur.fetchone()
    if row:
        _my_user_id = int(row[0])
    return _my_user_id


async def init_db():
    database = await aiosqlite.connect(DB_PATH)
    await database.execute("PRAGMA journal_mode=WAL;")
    await database.execute("PRAGMA synchronous=NORMAL;")
    await database.execute("PRAGMA temp_store=MEMORY;")
    await database.execute(
        "CREATE TABLE IF NOT EXISTS profiles ("
        "user_id INTEGER PRIMARY KEY, username TEXT, name TEXT, "
        "status TEXT DEFAULT 'active', is_me INTEGER DEFAULT 0, "
        "bot_mode INTEGER DEFAULT 0, hobbies TEXT DEFAULT '')"
    )
    try:
        await database.execute(
            "ALTER TABLE profiles ADD COLUMN communication_style TEXT DEFAULT 'formal'"
        )
    except Exception:
        pass
    try:
        await database.execute(
            "ALTER TABLE profiles ADD COLUMN selected_prompt TEXT DEFAULT ''"
        )
    except Exception:
        pass
    await database.execute(
        "CREATE TABLE IF NOT EXISTS messages ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER, "
        "sender_id INTEGER, text TEXT, "
        "timestamp DATETIME DEFAULT CURRENT_TIMESTAMP, "
        "tg_msg_id INTEGER)"
    )
    try:
        await database.execute(
            "ALTER TABLE messages ADD COLUMN tg_msg_id INTEGER"
        )
    except Exception:
        pass
    await database.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_messages_chat_tg "
        "ON messages(chat_id, tg_msg_id) WHERE tg_msg_id IS NOT NULL"
    )
    await database.execute(
        "CREATE TABLE IF NOT EXISTS app_profile ("
        "id INTEGER PRIMARY KEY CHECK (id = 1), "
        "display_name TEXT DEFAULT '', "
        "age TEXT DEFAULT '', "
        "about TEXT DEFAULT '')"
    )
    await database.execute(
        "INSERT OR IGNORE INTO app_profile (id, display_name, age, about) "
        "VALUES (1, '', '', '')"
    )
    try:
        await database.execute(
            "ALTER TABLE app_profile ADD COLUMN selected_api TEXT DEFAULT 'groq'"
        )
    except Exception:
        pass
    await database.commit()
    return database


async def get_app_profile():
    async with db.execute(
        "SELECT display_name, age, about, selected_api FROM app_profile WHERE id=1"
    ) as cur:
        row = await cur.fetchone()
    if not row:
        return {"display_name": "", "age": "", "about": "", "selected_api": "groq"}
    return {
        "display_name": row[0] or "",
        "age": row[1] or "",
        "about": row[2] or "",
        "selected_api": row[3] or "groq",
    }


async def save_app_profile(display_name, age, about, selected_api=None):
    if selected_api is not None:
        await db.execute(
            "UPDATE app_profile SET display_name=?, age=?, about=?, selected_api=? WHERE id=1",
            (display_name, age, about, selected_api),
        )
    else:
        await db.execute(
            "UPDATE app_profile SET display_name=?, age=?, about=? WHERE id=1",
            (display_name, age, about),
        )
    await db.commit()


async def get_profile_bio_text():
    from core.config import conf

    profile = await get_app_profile()
    if conf.get("LANGUAGE", "ru") == "en":
        header = "My profile (message author):"
        name_l, age_l, about_l = "Name", "Age", "About"
    else:
        header = "Мой профиль (автор сообщений):"
        name_l, age_l, about_l = "Имя", "Возраст", "О себе"

    parts = []
    if profile["display_name"]:
        parts.append(f"{name_l}: {profile['display_name']}")
    if profile["age"]:
        parts.append(f"{age_l}: {profile['age']}")
    if profile["about"]:
        parts.append(f"{about_l}: {profile['about']}")
    if not parts:
        return ""
    return f"{header}\n" + "\n".join(parts)


async def get_prompt_for_chat(chat_id):
    from core.config import conf
    async with db.execute(
        "SELECT bot_mode, selected_prompt FROM profiles WHERE user_id=?",
        (chat_id,),
    ) as cur:
        row = await cur.fetchone()
    
    prompts = conf.get("PROMPTS", {})
    if not row:
        if prompts:
            return list(prompts.values())[0]
        return ""
        
    bot_mode, selected_prompt = row
    if selected_prompt and selected_prompt in prompts:
        return prompts[selected_prompt]
        
    prompt_names = list(prompts.keys())
    if bot_mode is not None and 0 <= bot_mode < len(prompt_names):
        return prompts[prompt_names[bot_mode]]
        
    if prompts:
        return list(prompts.values())[0]
    return ""
