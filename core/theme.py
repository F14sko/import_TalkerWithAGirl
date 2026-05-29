from core import config
from core.config import tr


def palette(name=None):
    key = (name or config.conf.get("THEME", "dark")).strip().lower()
    if key == "light":
        return {
            "bg": "#FFFFFF",
            "panel": "#EAEBED",
            "text": "#006989",
            "muted": "#4d8a9a",
            "accent": "#006989",
            "input_bg": "#FFFFFF",
            "input_text": "#006989",
            "messages_bg": "#FFFFFF",
            "messages_text": "#006989",
            "selected_bg": "#d5dde0",
            "chat_list_bg": "#d5dde0",
            "chat_item_selected": "#c5d0d4",
            "btn_inactive_bg": "#c5d0d4",
            "btn_inactive_text": "#006989",
            "scrollbar_bg": "#EAEBED",
            "scrollbar_handle": "#b8c5ca",
            "avatar_bg": "#c5d0d4",
            "error_bg": "#FFFFFF",
            "error_text": "#006989",
            "bubble_peer_bg": "#d5dde0",
            "bubble_peer_text": "#006989",
            "bubble_mine_bg": "#006989",
            "bubble_mine_text": "#ffffff",
        }
    return {
        "bg": "#1a1a1a",
        "panel": "#222222",
        "text": "#ffffff",
        "muted": "#888888",
        "accent": "#ff9800",
        "input_bg": "#333333",
        "input_text": "#ffffff",
        "messages_bg": "#222222",
        "messages_text": "#dddddd",
        "selected_bg": "#2a2a2a",
        "chat_list_bg": "#2d2d2d",
        "chat_item_selected": "#3a3a3a",
        "btn_inactive_bg": "#444444",
        "btn_inactive_text": "#ffffff",
        "scrollbar_bg": "#222222",
        "scrollbar_handle": "#444444",
        "avatar_bg": "#333333",
        "error_bg": "#ffffff",
        "error_text": "#000000",
        "bubble_peer_bg": "#333333",
        "bubble_peer_text": "#dddddd",
        "bubble_mine_bg": "#ff9800",
        "bubble_mine_text": "#ffffff",
    }


def theme_label():
    if config.conf.get("THEME", "dark") == "light":
        return tr("theme_light")
    return tr("theme_dark")
