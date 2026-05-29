import shutil
from pathlib import Path

from core.config import IMAGE_PATH, PROJECT_ROOT

ASSETS_DIR = PROJECT_ROOT / "avatar"
_LEGACY_ACCOUNT_DIR = PROJECT_ROOT / "acount"


def ensure_assets_dir():
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)


def migrate_legacy_account_dir():
    if not _LEGACY_ACCOUNT_DIR.exists():
        return
    ensure_assets_dir()
    for item in _LEGACY_ACCOUNT_DIR.iterdir():
        if not item.is_file():
            continue
        dest = ASSETS_DIR / item.name
        if dest.exists():
            item.unlink(missing_ok=True)
        else:
            shutil.move(str(item), str(dest))
    try:
        _LEGACY_ACCOUNT_DIR.rmdir()
    except OSError:
        shutil.rmtree(_LEGACY_ACCOUNT_DIR, ignore_errors=True)


migrate_legacy_account_dir()


def default_avatar_path():
    if IMAGE_PATH.exists() and IMAGE_PATH.stat().st_size > 0:
        return IMAGE_PATH
    return None


def has_user_avatar(user_id):
    ensure_assets_dir()
    for ext in (".jpg", ".jpeg", ".png"):
        path = ASSETS_DIR / f"{user_id}{ext}"
        if path.exists() and path.stat().st_size > 0:
            return True
    return False


def avatar_file(user_id):
    ensure_assets_dir()
    for ext in (".jpg", ".jpeg", ".png"):
        path = ASSETS_DIR / f"{user_id}{ext}"
        if path.exists() and path.stat().st_size > 0:
            return path
    return default_avatar_path()


def avatar_save_path(user_id):
    ensure_assets_dir()
    return ASSETS_DIR / f"{user_id}.jpg"


def delete_avatar(user_id):
    ensure_assets_dir()
    for ext in (".jpg", ".jpeg", ".png"):
        path = ASSETS_DIR / f"{user_id}{ext}"
        if path.exists():
            path.unlink(missing_ok=True)


def _remove_empty_file(path):
    p = Path(path)
    if p.exists() and p.stat().st_size == 0:
        p.unlink(missing_ok=True)


async def download_chat_avatar(user_id):
    from core import telegram_bot

    client = telegram_bot.client
    if not client or not client.is_connected():
        return None

    path = avatar_save_path(user_id)
    try:
        from core.database import get_my_user_id
        my_id = get_my_user_id()
        if my_id and user_id == my_id:
            entity = "me"
        else:
            entity = await client.get_entity(user_id)
        ensure_assets_dir()
        result = await client.download_profile_photo(entity, file=str(path))
        if result:
            _remove_empty_file(result)
            result_path = Path(result)
            if result_path.exists() and result_path.stat().st_size > 0:
                return result_path
        _remove_empty_file(path)
        if path.exists() and path.stat().st_size > 0:
            return path
    except Exception:
        _remove_empty_file(path)

    return None
