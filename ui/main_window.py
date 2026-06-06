import asyncio
from datetime import datetime

from PyQt6.QtCore import Qt, QTimer

try:
    from PyQt6 import sip
except ImportError:
    import sip
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QFrame,
    QLineEdit,
    QTextEdit,
    QComboBox,
    QSizePolicy,
    QListView,
)

from core import config
from core import database
from core import telegram_bot
from core.config import language_label, save_config, tr
from core.theme import palette, theme_label
from core.avatars import delete_avatar, download_chat_avatar, has_user_avatar
from core.database import (
    get_app_profile,
    get_my_user_id,
    get_profile_bio_text,
    init_db,
    resolve_my_user_id,
    save_app_profile,
)
from core.avatars import avatar_file, default_avatar_path
from core.ai import call_groq_api, generate_ai_summary
from core.utils import (
    format_message_time_local,
    store_message_timestamp,
    timezone_offset_hours,
)
from core.telegram_bot import start_client, stop_client
from ui.widgets import (
    signals,
    ChatItem,
    ChatMessagesView,
    RestrictedScrollArea,
    AddChatDialog,
    apply_rounded_mask,
    rounded_pixmap,
)

WIN_W = int(1440 * 0.75)
WIN_H = int(800 * 2 / 3)
WIN_H += WIN_H // 3
HEADER_H = 68
WIN_RADIUS = 16


class ToolTipPopup(QWidget):
    def __init__(self, text, parent_app, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(300, 130)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        self.frame = QFrame()
        frame_layout = QVBoxLayout(self.frame)
        frame_layout.setContentsMargins(12, 12, 12, 12)
        
        self.label = QLabel(text)
        self.label.setWordWrap(True)
        self.label.setStyleSheet("background: transparent; border: none;")
        frame_layout.addWidget(self.label)
        
        layout.addWidget(self.frame)
        
        t = parent_app.t
        accent = t["accent"]
        panel = t["panel"]
        text_color = t["text"]
        
        self.frame.setStyleSheet(
            f"QFrame {{ background-color: {panel}; "
            f"border: 1px solid {accent}; border-radius: 10px; }}"
            f"QLabel {{ color: {text_color}; font-size: 12px; font-weight: normal; }}"
        )


class HelpIcon(QLabel):
    def __init__(self, text, tooltip_text, parent_app, parent=None):
        super().__init__(text, parent)
        self.tooltip_text = tooltip_text
        self.parent_app = parent_app
        self.popup = None
        self.setFixedSize(16, 16)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMouseTracking(True)
        self.setObjectName("helpIcon")

    def enterEvent(self, event):
        if not self.popup:
            self.popup = ToolTipPopup(self.tooltip_text, self.parent_app)
        
        global_pos = self.mapToGlobal(self.rect().topLeft())
        self.popup.move(global_pos.x() + 12, global_pos.y() - 120)
        self.popup.show()
        super().enterEvent(event)

    def leaveEvent(self, event):
        if self.popup:
            self.popup.hide()
            self.popup.deleteLater()
            self.popup = None
        super().leaveEvent(event)


class MainApp(QWidget):
    def __init__(self):
        super().__init__()
        self.t = palette()
        self.is_running = False
        self.active_chat_id = None
        self.active_chat_name = ""
        self.current_tab = "chats"
        self.split_visible = False
        self.right_mode = None
        self.chat_items = {}
        self._messages_cache = {}
        self._profile_load_gen = 0
        self.chat_subview = "messages"
        self.settings_tab = "general"
        self.window_drag_pos = None

        self.initUI()

        signals.chat_list_updated.connect(self.refresh_chats)
        signals.data_loaded.connect(self.render_chat_list)
        signals.status_changed.connect(self.update_bot_status_ui)
        signals.update_summary_signal.connect(self.set_summary_text_safe)
        signals.error_signal.connect(self.show_error)
        signals.chat_settings_ready.connect(self._on_chat_settings_ready)
        signals.avatar_updated.connect(self._on_avatar_updated)
        signals.messages_loaded.connect(self._on_messages_loaded)
        signals.profile_loaded.connect(self._on_profile_loaded)

        QTimer.singleShot(500, self.refresh_chats)

    def _input_style(self):
        return (
            f"background: {self.t['input_bg']}; color: {self.t['input_text']}; "
            f"border: none; border-radius: 10px; padding: 10px; font-size: 14px;"
        )

    def _combo_style(self):
        bg = self.t["input_bg"]
        text = self.t["input_text"]
        border = self.t["scrollbar_handle"]
        accent = self.t["accent"]
        return (
            f"QComboBox {{ background-color: {bg}; color: {text}; "
            f"border: 1px solid {border}; border-radius: 10px; padding: 8px 12px; font-size: 14px; }}"
            f"QComboBox::drop-down {{ border: none; }}"
            f"QComboBox QListView {{ background-color: {bg}; color: {text}; "
            f"border: 1px solid {border}; border-radius: 10px; "
            f"selection-background-color: {accent}; selection-color: white; outline: 0px; }}"
        )

    def _btn_filled_style(self):
        return (
            f"background-color: {self.t['accent']}; color: white; border: none; "
            f"border-radius: 12px; font-size: 14px; font-weight: bold; padding: 10px 16px;"
        )

    def _btn_grey_style(self):
        return (
            f"background-color: {self.t['btn_inactive_bg']}; "
            f"color: {self.t['btn_inactive_text']}; border: none; "
            f"border-radius: 12px; font-size: 14px; font-weight: bold; padding: 10px 16px;"
        )

    def _btn_outline_style(self):
        acc = self.t["accent"]
        return (
            f"background-color: transparent; color: {acc}; border: 2px solid {acc}; "
            f"border-radius: 12px; font-size: 14px; font-weight: bold; padding: 8px 18px;"
        )

    def _scrollbar_style(self):
        bg = self.t["bg"]
        text_color = self.t["text"]
        panel = self.t["panel"]
        accent = self.t["accent"]
        return (
            "QScrollBar:vertical { width: 0px; background: transparent; border: none; }"
            "QScrollBar:horizontal { height: 0px; background: transparent; border: none; }"
            "QScrollBar::handle:vertical, QScrollBar::handle:horizontal { background: transparent; border: none; }"
            "QScrollBar::add-line, QScrollBar::sub-line { width: 0px; height: 0px; }"
            f"QToolTip {{ background-color: {panel}; color: {text_color}; "
            f"border: 1px solid {accent}; border-radius: 6px; padding: 8px; "
            f"font-size: 12px; font-weight: normal; }}"
        )

    def _panel_card_style(self, bg_color):
        border = self.t["scrollbar_handle"]
        return (
            f"QFrame {{ background-color: {bg_color}; border: 1px solid {border}; "
            f"border-radius: 18px; }}"
        )

    def _label_style(self, size=14, muted=False):
        color = self.t["muted"] if muted else self.t["text"]
        return (
            f"color: {color}; font-size: {size}px; font-weight: bold; "
            f"border: none; outline: none; background: transparent; padding: 0px;"
        )

    def _title_style(self, size=20):
        return (
            f"color: {self.t['text']}; font-size: {size}px; font-weight: bold; "
            f"border: none; outline: none; background: transparent; padding: 0px;"
        )

    def _chat_list_box_style(self):
        border = self.t["scrollbar_handle"]
        bg = self.t.get("chat_list_bg", self.t["panel"])
        return (
            f"QFrame#chatListFrame {{ background-color: {bg}; "
            f"border: 1px solid {border}; border-radius: 14px; }}"
        )

    def _chat_list_separator_style(self):
        border = self.t["scrollbar_handle"]
        return f"background-color: {border}; border: none;"

    def _messages_box_style(self):
        return (
            f"background: {self.t['input_bg']}; color: {self.t['input_text']}; "
            f"border-radius: 10px; padding: 12px; font-size: 13px; border: none;"
        )

    def _main_frame_style(self):
        bg = self.t["bg"]
        return (
            f"QFrame#mainFrame {{ background-color: {bg}; "
            f"border-radius: {WIN_RADIUS}px; }}"
            f"QLabel {{ color: {self.t['text']}; background: transparent; "
            f"border: none; outline: none; padding: 0px; }}"
        )

    def _is_alive(self, widget):
        if widget is None:
            return False
        try:
            return not sip.isdeleted(widget)
        except Exception:
            return True

    def apply_theme(self):
        self.t = palette()
        self.setStyleSheet(self._scrollbar_style())
        self.main_frame.setStyleSheet(self._main_frame_style())
        QTimer.singleShot(0, lambda: apply_rounded_mask(self.main_frame, WIN_RADIUS))
        if hasattr(self, "header_frame"):
            self.header_frame.setStyleSheet(
                f"background-color: {self.t['bg']};"
            )
        self.left_panel.setStyleSheet(self._panel_card_style(self.t["panel"]))
        if hasattr(self, "scroll_content"):
            self.scroll_content.setStyleSheet(
                f"background-color: transparent;"
            )
        if hasattr(self, "chat_list_frame"):
            self.chat_list_frame.setStyleSheet(self._chat_list_box_style())
        self.right_panel.setStyleSheet(self._panel_card_style(self.t["panel"]))
        self.title.setStyleSheet(self._title_style(22))
        self._apply_conn_button_style()
        self._update_tab_styles()
        self.chats_title.setStyleSheet(self._title_style(18))
        self.new_chat_btn.setStyleSheet(
            f"color: {self.t['accent']}; background: transparent; border: none; "
            f"font-size: 14px; font-weight: bold;"
        )
        self.close_btn.setStyleSheet(
            f"color: {self.t['accent']}; border: none; font-size: 18px;"
        )
        self.status_lbl.setStyleSheet(
            f"color: {self.t['muted'] if not self.is_running else self.t['accent']}; "
            f"font-size: 13px; font-weight: bold; border: none; outline: none; "
            f"background: transparent; padding: 0px;"
        )
        if hasattr(self, "error_label"):
            self.error_label.setStyleSheet(
                f"background-color: {self.t['error_bg']}; color: {self.t['error_text']}; "
                f"border-radius: 12px; font-size: 14px; font-weight: bold;"
            )
        if self.split_visible:
            snap = self._capture_right_panel_state()
            self._rebuild_right_panel()
            self._restore_right_panel_state(snap)
        if self._is_alive(getattr(self, "messages_view", None)):
            self.messages_view.apply_theme_style()
        if self._is_alive(getattr(self, "profile_avatar", None)):
            self._refresh_profile_avatar()
        if self._is_alive(getattr(self, "lang_toggle_btn", None)):
            self.lang_toggle_btn.setStyleSheet(self._btn_outline_style())
        if self._is_alive(getattr(self, "theme_toggle_btn", None)):
            self.theme_toggle_btn.setText(theme_label())
            self.theme_toggle_btn.setStyleSheet(self._btn_outline_style())
        self.render_chat_list_from_cache()

    def _widget_text(self, widget, plain=False):
        if not self._is_alive(widget):
            return None
        if isinstance(widget, QComboBox):
            return widget.currentData()
        return widget.toPlainText() if plain else widget.text()

    def _capture_right_panel_state(self):
        state = {}
        if not self.split_visible:
            return state

        if self.right_mode == "settings":
            for key, attr, plain in (
                ("api_id", "api_id_input", False),
                ("api_hash", "api_hash_input", False),
                ("api_key", "key_input", False),
                ("timezone", "timezone_combo", False),
                ("selected_api", "api_combo", False),
                ("p_intro", "p_intro", True),
                ("p_chat", "p_chat", True),
            ):
                val = self._widget_text(getattr(self, attr, None), plain)
                if val is not None:
                    state[key] = val

        elif self.right_mode == "profile":
            for key, attr, plain in (
                ("profile_name", "profile_name_input", False),
                ("profile_age", "profile_age_input", False),
                ("profile_about", "profile_about_input", True),
            ):
                val = self._widget_text(getattr(self, attr, None), plain)
                if val is not None:
                    state[key] = val

        elif self.right_mode == "chat" and self.chat_subview == "settings":
            val = self._widget_text(getattr(self, "date_input", None), False)
            if val is not None:
                state["date"] = val
            val = self._widget_text(getattr(self, "summary_text", None), True)
            if val is not None:
                state["summary"] = val

        return state

    def _restore_right_panel_state(self, state):
        if not state:
            return

        if self.right_mode == "settings":
            mapping = (
                ("api_id", "api_id_input", False),
                ("api_hash", "api_hash_input", False),
                ("api_key", "key_input", False),
                ("timezone", "timezone_combo", False),
                ("selected_api", "api_combo", False),
                ("p_intro", "p_intro", True),
                ("p_chat", "p_chat", True),
            )
            for key, attr, plain in mapping:
                if key not in state:
                    continue
                w = getattr(self, attr, None)
                if self._is_alive(w):
                    if isinstance(w, QComboBox):
                        idx = w.findData(state[key])
                        if idx >= 0:
                            w.setCurrentIndex(idx)
                    elif plain:
                        w.setPlainText(state[key])
                    else:
                        w.setText(state[key])

        elif self.right_mode == "profile":
            loaded = False
            for key, attr, plain in (
                ("profile_name", "profile_name_input", False),
                ("profile_age", "profile_age_input", False),
                ("profile_about", "profile_about_input", True),
            ):
                if key not in state:
                    continue
                w = getattr(self, attr, None)
                if self._is_alive(w):
                    if plain:
                        w.setPlainText(state[key])
                    else:
                        w.setText(state[key])
                    loaded = True
            if not loaded:
                self._load_profile_fields()

        elif self.right_mode == "chat" and self.chat_subview == "settings":
            if "date" in state and self._is_alive(getattr(self, "date_input", None)):
                self.date_input.setText(state["date"])
            if "summary" in state and self._is_alive(getattr(self, "summary_text", None)):
                self.summary_text.setPlainText(state["summary"])
            if self.active_chat_id:
                self._apply_chat_settings_from_db()

    def render_chat_list_from_cache(self):
        if hasattr(self, "_last_users"):
            self.render_chat_list(self._last_users)
        else:
            self.refresh_chat_items_theme()

    def toggle_theme(self):
        current = config.conf.get("THEME", "dark")
        config.conf["THEME"] = "light" if current == "dark" else "dark"
        save_config(config.conf)
        self.apply_theme()

    def _media_reply_label(self):
        val = config.conf.get("EXPERIMENTAL_MEDIA_REPLY", False)
        return tr("media_reply_on") if val else tr("media_reply_off")

    def _media_reply_btn_style(self):
        val = config.conf.get("EXPERIMENTAL_MEDIA_REPLY", False)
        return self._btn_filled_style() if val else self._btn_outline_style()

    def toggle_media_reply(self):
        val = config.conf.get("EXPERIMENTAL_MEDIA_REPLY", False)
        config.conf["EXPERIMENTAL_MEDIA_REPLY"] = not val
        save_config(config.conf)
        if hasattr(self, "media_reply_toggle_btn") and self.media_reply_toggle_btn:
            self.media_reply_toggle_btn.setText(self._media_reply_label())
            self.media_reply_toggle_btn.setStyleSheet(self._media_reply_btn_style())

    def initUI(self):
        self.setFixedSize(WIN_W, WIN_H)
        self.setWindowTitle("FiaskoAI")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet(self._scrollbar_style())

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.main_frame = QFrame()
        self.main_frame.setObjectName("mainFrame")
        self.main_frame.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.main_frame.setStyleSheet(f"background-color: {self.t['bg']};")
        root.addWidget(self.main_frame)

        main_layout = QVBoxLayout(self.main_frame)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self._build_header(main_layout)
        self._build_body(main_layout)
        self.apply_theme()

        self.error_label = QLabel(self.main_frame)
        self.error_label.setGeometry(40, 10, 360, 40)
        self.error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.error_label.setStyleSheet(
            f"background-color: {self.t['error_bg']}; color: {self.t['error_text']}; "
            f"border-radius: 12px; font-size: 14px; font-weight: bold;"
        )
        self.error_label.hide()

    def _make_outline_button(self, text):
        btn = QPushButton(text)
        btn.setStyleSheet(self._btn_outline_style())
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        return btn

    def _apply_conn_button_style(self):
        if self.is_running:
            self.conn_btn.setText(tr("disconnect"))
            self.conn_btn.setStyleSheet(self._btn_outline_style())
        else:
            self.conn_btn.setText(tr("connect"))
            self.conn_btn.setStyleSheet(self._btn_filled_style())

    def animate_button_press(self, button, duration_ms=1000):
        original = button.styleSheet()
        darker = (
            original.replace("#ff9800", "#c47a00")
            .replace("#444444", "#2a2a2a")
            .replace("#444", "#2a2a2a")
            .replace(
                "background-color: transparent",
                "background-color: rgba(255, 152, 0, 0.15)",
            )
        )
        button.setStyleSheet(darker)

        def restore():
            if button is self.conn_btn:
                self._apply_conn_button_style()
            else:
                button.setStyleSheet(original)

        QTimer.singleShot(duration_ms, restore)

    def _connect_action_with_press(self, button, action):
        def on_click():
            self.animate_button_press(button)
            action()

        button.clicked.connect(on_click)

    def _build_header(self, parent_layout):
        self.header_frame = QFrame()
        self.header_frame.setFixedHeight(HEADER_H)
        self.header_frame.setStyleSheet(f"background-color: {self.t['bg']};")
        header = self.header_frame
        h = QHBoxLayout(header)
        h.setContentsMargins(24, 12, 24, 12)
        h.setSpacing(20)

        brand = QVBoxLayout()
        brand.setSpacing(2)
        self.title = QLabel("FiaskoAI")
        self.title.setStyleSheet(self._title_style(22))
        self.status_lbl = QLabel("offline")
        self.status_lbl.setStyleSheet(self._label_style(13, muted=True))
        brand.addWidget(self.title)
        brand.addWidget(self.status_lbl)
        h.addLayout(brand)

        h.addSpacing(40)

        self.tab_chats_btn = self._make_tab_button(tr("tab_chats"))
        self.tab_settings_btn = self._make_tab_button(tr("tab_settings"))
        self.tab_profile_btn = self._make_tab_button(tr("tab_profile"))
        self.tab_chats_btn.clicked.connect(lambda: self.select_tab("chats"))
        self.tab_settings_btn.clicked.connect(lambda: self.select_tab("settings"))
        self.tab_profile_btn.clicked.connect(lambda: self.select_tab("profile"))
        h.addWidget(self.tab_chats_btn)
        h.addWidget(self.tab_settings_btn)
        h.addWidget(self.tab_profile_btn)

        h.addStretch()

        self.conn_btn = QPushButton(tr("connect"))
        self.conn_btn.setFixedHeight(40)
        self.conn_btn.clicked.connect(self.toggle_bot)
        self._apply_conn_button_style()
        h.addWidget(self.conn_btn)

        self.close_btn = QPushButton("✕")
        self.close_btn.setFixedSize(36, 36)
        self.close_btn.setStyleSheet(
            f"color: {self.t['accent']}; border: none; font-size: 18px;"
        )
        self.close_btn.clicked.connect(self.close)
        h.addWidget(self.close_btn)

        parent_layout.addWidget(header)
        self._update_tab_styles()

    def _make_tab_button(self, text):
        btn = QPushButton(text)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        muted = self.t["muted"]
        text_c = self.t["text"]
        btn.setStyleSheet(
            f"QPushButton {{ color: {muted}; border: none; font-size: 15px; "
            f"font-weight: bold; padding: 8px 4px; background: transparent; }}"
            f"QPushButton:hover {{ color: {text_c}; }}"
        )
        return btn

    def _update_tab_styles(self):
        tabs = {
            "chats": self.tab_chats_btn,
            "settings": self.tab_settings_btn,
            "profile": self.tab_profile_btn,
        }
        muted = self.t["muted"]
        text_c = self.t["text"]
        for key, btn in tabs.items():
            if key == self.current_tab:
                btn.setStyleSheet(
                    f"QPushButton {{ color: {text_c}; border: none; font-size: 15px; "
                    f"font-weight: bold; padding: 8px 4px; background: transparent; "
                    f"border-bottom: 2px solid {self.t['accent']}; }}"
                )
            else:
                btn.setStyleSheet(
                    f"QPushButton {{ color: {muted}; border: none; font-size: 15px; "
                    f"font-weight: bold; padding: 8px 4px; background: transparent; }}"
                    f"QPushButton:hover {{ color: {text_c}; }}"
                )

    def _build_body(self, parent_layout):
        body = QHBoxLayout()
        body.setContentsMargins(16, 16, 16, 16)
        body.setSpacing(16)

        self.left_panel = QFrame()
        self.left_panel.setStyleSheet(self._panel_card_style(self.t["panel"]))
        left_layout = QVBoxLayout(self.left_panel)
        left_layout.setContentsMargins(20, 16, 12, 16)
        left_layout.setSpacing(12)

        list_header = QHBoxLayout()
        self.chats_title = QLabel(tr("tab_chats"))
        self.chats_title.setStyleSheet(self._title_style(18))
        list_header.addWidget(self.chats_title)
        list_header.addStretch()
        self.new_chat_btn = QPushButton(tr("new_chat"))
        self.new_chat_btn.setStyleSheet(
            f"color: {self.t['accent']}; background: transparent; border: none; "
            f"font-size: 14px; font-weight: bold;"
        )
        self.new_chat_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.new_chat_btn.clicked.connect(self.prompt_add_chat)
        list_header.addWidget(self.new_chat_btn)
        left_layout.addLayout(list_header)

        self.scroll = RestrictedScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet("border: none; background: transparent;")
        self.scroll_content = QWidget()
        scroll_outer = QVBoxLayout(self.scroll_content)
        scroll_outer.setContentsMargins(0, 0, 0, 12)
        scroll_outer.setSpacing(0)

        self.chat_list_frame = QFrame()
        self.chat_list_frame.setObjectName("chatListFrame")
        self.chat_list_frame.setStyleSheet(self._chat_list_box_style())
        self.chat_list_frame.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Maximum,
        )
        self.chat_layout = QVBoxLayout(self.chat_list_frame)
        self.chat_layout.setContentsMargins(0, 0, 0, 0)
        self.chat_layout.setSpacing(0)

        scroll_outer.addWidget(self.chat_list_frame, 0, Qt.AlignmentFlag.AlignTop)
        scroll_outer.addStretch(1)
        self.scroll.setWidget(self.scroll_content)
        left_layout.addWidget(self.scroll)

        self.right_panel = QFrame()
        self.right_panel.setStyleSheet(self._panel_card_style(self.t["panel"]))
        self.right_layout = QVBoxLayout(self.right_panel)
        self.right_layout.setContentsMargins(24, 20, 24, 20)
        self.right_layout.setSpacing(12)
        self.right_panel.hide()

        body.addWidget(self.left_panel, 1)
        body.addWidget(self.right_panel, 1)

        parent_layout.addLayout(body, 1)

    def _clear_chat_list_selection(self):
        for item in self.chat_items.values():
            item.set_selected(False)

    def _restore_chat_list_selection(self):
        if self.current_tab != "chats" or not self.active_chat_id:
            return
        for uid, item in self.chat_items.items():
            item.set_selected(uid == self.active_chat_id)

    def select_tab(self, tab):
        self.current_tab = tab
        self._update_tab_styles()

        if tab == "settings":
            self._clear_chat_list_selection()
            self.show_split("settings")
        elif tab == "profile":
            self._clear_chat_list_selection()
            self.show_split("profile")
        elif tab == "chats":
            if self.active_chat_id:
                self.show_split("chat")
                self._restore_chat_list_selection()
            else:
                self._clear_chat_list_selection()
                self.hide_split()

    def show_split(self, right_mode):
        self.split_visible = True
        self.update_chat_items_truncation()
        self.right_mode = right_mode
        self.right_panel.show()
        self._rebuild_right_panel()
        if right_mode == "profile":
            self._load_profile_fields()

    def hide_split(self):
        self.split_visible = False
        self.update_chat_items_truncation()
        self.right_mode = None
        self.right_panel.hide()

    def update_chat_items_truncation(self):
        for item in self.chat_items.values():
            if hasattr(item, "update_name_truncation"):
                item.update_name_truncation()

    def select_chat(self, user_id, name):
        self.active_chat_id = user_id
        self.active_chat_name = name
        self.chat_subview = "messages"
        self.current_tab = "chats"
        self._update_tab_styles()
        for uid, item in self.chat_items.items():
            item.set_selected(uid == user_id)
        self.show_split("chat")

    def clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self.clear_layout(item.layout())

    def _clear_panel_widget_refs(self):
        for attr in (
            "api_id_input",
            "api_hash_input",
            "key_input",
            "p_intro",
            "p_chat",
            "lang_toggle_btn",
            "theme_toggle_btn",
            "timezone_combo",
            "chat_title_lbl",
            "chat_gear_btn",
            "formal_btn",
            "casual_btn",
            "prompt_intro_btn",
            "prompt_chat_btn",
            "date_input",
            "summary_text",
            "media_reply_toggle_btn",
            "api_id_input",
            "api_hash_input",
            "key_input",
            "timezone_combo",
            "api_combo",
            "settings_general_btn",
            "settings_prompts_btn",
            "_prompt_edits",
            "chat_prompt_combo",
        ):
            if hasattr(self, attr):
                setattr(self, attr, None)

    def _rebuild_right_panel(self):
        self._profile_load_gen += 1
        self._clear_panel_widget_refs()
        self.clear_layout(self.right_layout)

        if self.right_mode == "settings":
            self._build_settings_panel()
        elif self.right_mode == "profile":
            self._build_profile_panel()
        elif self.right_mode == "chat" and self.active_chat_id:
            if self.chat_subview == "settings":
                self._build_chat_settings_panel()
            else:
                self._build_chat_messages_panel()

    def _add_panel_header(self, title_text, save_callback=None):
        row = QHBoxLayout()
        title = QLabel(title_text)
        title.setStyleSheet(self._title_style(20))
        row.addWidget(title)
        row.addStretch()
        if save_callback:
            save_btn = self._make_outline_button(tr("save"))
            save_btn.clicked.connect(save_callback)
            row.addWidget(save_btn)
        self.right_layout.addLayout(row)

    def open_chat_settings(self):
        self.chat_subview = "settings"
        if self.split_visible and self.right_mode == "chat":
            self._rebuild_right_panel()

    def back_to_chat_messages(self):
        self.chat_subview = "messages"
        if self.split_visible and self.right_mode == "chat":
            self._rebuild_right_panel()

    def _build_settings_panel(self):
        self._add_panel_header(tr("tab_settings"), self.save_settings)

        # Tab switcher layout
        tabs_layout = QHBoxLayout()
        tabs_layout.setContentsMargins(0, 5, 0, 10)
        tabs_layout.setSpacing(20)

        text_c = self.t["text"]
        muted = self.t["muted"]
        accent = self.t["accent"]

        self.settings_general_btn = QPushButton(tr("settings_general"))
        self.settings_prompts_btn = QPushButton(tr("settings_prompts"))

        for btn, tab_name in [(self.settings_general_btn, "general"), (self.settings_prompts_btn, "prompts")]:
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            if self.settings_tab == tab_name:
                btn.setStyleSheet(
                    f"QPushButton {{ color: {text_c}; border: none; font-size: 14px; "
                    f"font-weight: bold; padding: 6px 0px; background: transparent; "
                    f"border-bottom: 2px solid {accent}; }}"
                )
            else:
                btn.setStyleSheet(
                    f"QPushButton {{ color: {muted}; border: none; font-size: 14px; "
                    f"font-weight: bold; padding: 6px 0px; background: transparent; }}"
                    f"QPushButton:hover {{ color: {text_c}; }}"
                )
            
        def select_settings_tab(tab_name):
            self.settings_tab = tab_name
            self._rebuild_right_panel()

        self.settings_general_btn.clicked.connect(lambda: select_settings_tab("general"))
        self.settings_prompts_btn.clicked.connect(lambda: select_settings_tab("prompts"))

        tabs_layout.addWidget(self.settings_general_btn)
        tabs_layout.addWidget(self.settings_prompts_btn)
        tabs_layout.addStretch()
        self.right_layout.addLayout(tabs_layout)

        if self.settings_tab == "general":
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            scroll.setStyleSheet(
                f"border: none; background: {self.t['panel']};"
            )
            content = QWidget()
            content.setStyleSheet(f"background: {self.t['panel']};")
            layout = QVBoxLayout(content)
            layout.setSpacing(10)
            config_row = QHBoxLayout()

            theme_col = QVBoxLayout()
            theme_lbl = QLabel(tr("theme"))
            theme_lbl.setStyleSheet(self._label_style())
            self.theme_toggle_btn = QPushButton(theme_label())
            self.theme_toggle_btn.setStyleSheet(self._btn_outline_style())
            self.theme_toggle_btn.clicked.connect(self.toggle_theme)
            theme_col.addWidget(theme_lbl)
            theme_col.addWidget(self.theme_toggle_btn)
            config_row.addLayout(theme_col)

            config_row.addStretch()

            lang_col = QVBoxLayout()
            lang_lbl = QLabel(tr("language"))
            lang_lbl.setStyleSheet(self._label_style())
            lang_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
            self.lang_toggle_btn = QPushButton(
                language_label(config.conf.get("LANGUAGE", "en"))
            )
            self.lang_toggle_btn.setStyleSheet(self._btn_outline_style())
            self.lang_toggle_btn.clicked.connect(self.toggle_ui_language)
            
            lang_btn_row = QHBoxLayout()
            lang_btn_row.addStretch()
            lang_btn_row.addWidget(self.lang_toggle_btn)
            
            lang_col.addWidget(lang_lbl)
            lang_col.addLayout(lang_btn_row)
            config_row.addLayout(lang_col)

            layout.addLayout(config_row)

            tz_lbl = QLabel(tr("timezone"))
            tz_lbl.setStyleSheet(self._label_style())
            layout.addWidget(tz_lbl)
            self.timezone_combo = QComboBox()
            self.timezone_combo.setView(QListView())
            self.timezone_combo.setStyleSheet(self._combo_style())
            current_offset = timezone_offset_hours()
            for hour in range(-12, 15):
                label = f"UTC+{hour}" if hour >= 0 else f"UTC{hour}"
                self.timezone_combo.addItem(label, hour)
            idx = self.timezone_combo.findData(current_offset)
            self.timezone_combo.setCurrentIndex(idx if idx >= 0 else self.timezone_combo.findData(0))
            layout.addWidget(self.timezone_combo)

            api_lbl = QLabel(tr("selected_api"))
            api_lbl.setStyleSheet(self._label_style())
            layout.addWidget(api_lbl)
            self.api_combo = QComboBox()
            self.api_combo.setView(QListView())
            self.api_combo.setStyleSheet(self._combo_style())
            self.api_combo.addItem("Gemini", "gemini")
            self.api_combo.addItem("ChatGPT", "chatgpt")
            self.api_combo.addItem("Llama", "llama")
            self.api_combo.addItem("Groq", "groq")
            current_api = config.conf.get("SELECTED_API", "groq")
            idx = self.api_combo.findData(current_api)
            self.api_combo.setCurrentIndex(idx if idx >= 0 else self.api_combo.findData("groq"))
            layout.addWidget(self.api_combo)

            # Media reply toggle layout
            media_reply_layout = QVBoxLayout()
            media_reply_layout.setSpacing(4)
            
            label_layout = QHBoxLayout()
            label_layout.setSpacing(6)
            
            media_lbl = QLabel(tr("media_reply"))
            media_lbl.setStyleSheet(self._label_style())
            label_layout.addWidget(media_lbl)
            
            question_mark = HelpIcon("?", tr("media_reply_tooltip"), self)
            question_mark.setStyleSheet(
                f"QLabel#helpIcon {{ color: {self.t['muted']}; border: 1px solid {self.t['muted']}; "
                f"border-radius: 8px; font-size: 10px; font-weight: bold; background: transparent; }}"
            )
            label_layout.addWidget(question_mark)
            label_layout.addStretch()
            
            media_reply_layout.addLayout(label_layout)
            
            self.media_reply_toggle_btn = QPushButton(self._media_reply_label())
            self.media_reply_toggle_btn.setStyleSheet(self._media_reply_btn_style())
            self.media_reply_toggle_btn.clicked.connect(self.toggle_media_reply)
            media_reply_layout.addWidget(self.media_reply_toggle_btn)
            
            layout.addLayout(media_reply_layout)

            def add_field(label_text, widget):
                lbl = QLabel(label_text)
                lbl.setStyleSheet(self._label_style())
                layout.addWidget(lbl)
                layout.addWidget(widget)

            self.api_id_input = QLineEdit(str(config.conf["API_ID"]))
            self.api_id_input.setStyleSheet(self._input_style())
            add_field("API ID:", self.api_id_input)

            self.api_hash_input = QLineEdit(config.conf["API_HASH"])
            self.api_hash_input.setStyleSheet(self._input_style())
            add_field("API HASH:", self.api_hash_input)

            self.key_input = QLineEdit(config.conf["API_KEY"])
            self.key_input.setStyleSheet(self._input_style())
            add_field("API Key:", self.key_input)

            layout.addStretch()
            scroll.setWidget(content)
            self.right_layout.addWidget(scroll, 1)

        elif self.settings_tab == "prompts":
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            scroll.setStyleSheet(
                f"border: none; background: {self.t['panel']};"
            )
            content = QWidget()
            content.setStyleSheet(f"background: {self.t['panel']};")
            layout = QVBoxLayout(content)
            layout.setSpacing(15)

            header_row = QHBoxLayout()
            prompts_lbl = QLabel(tr("settings_prompts"))
            prompts_lbl.setStyleSheet(self._label_style(16))
            header_row.addWidget(prompts_lbl)
            
            header_row.addStretch()
            
            add_btn = self._make_outline_button(tr("add"))
            add_btn.clicked.connect(self.add_prompt_click)
            header_row.addWidget(add_btn)
            layout.addLayout(header_row)

            self._prompt_edits = {}
            prompts_dict = config.conf.get("PROMPTS", {})
            for name, text in prompts_dict.items():
                prompt_header = QHBoxLayout()
                lbl = QLabel(name)
                lbl.setStyleSheet(self._label_style(13))
                prompt_header.addWidget(lbl)
                
                prompt_header.addStretch()
                
                del_btn = QPushButton("✕")
                del_btn.setFixedSize(24, 24)
                del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                del_btn.setStyleSheet(
                    f"color: #aa3333; background: transparent; border: none; font-size: 14px; font-weight: bold;"
                )
                def make_delete_callback(p_name):
                    return lambda: self.delete_prompt(p_name)
                del_btn.clicked.connect(make_delete_callback(name))
                prompt_header.addWidget(del_btn)
                layout.addLayout(prompt_header)

                text_edit = QTextEdit(text)
                text_edit.setFixedHeight(120)
                text_edit.setStyleSheet(self._input_style())
                layout.addWidget(text_edit)
                self._prompt_edits[name] = text_edit

            layout.addStretch()
            scroll.setWidget(content)
            self.right_layout.addWidget(scroll, 1)

    def add_prompt_click(self):
        from ui.widgets import AddPromptDialog
        from PyQt6.QtWidgets import QDialog
        dlg = AddPromptDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            name, text = dlg.get_data()
            if name and text:
                if "PROMPTS" not in config.conf:
                    config.conf["PROMPTS"] = {}
                config.conf["PROMPTS"][name] = text
                save_config(config.conf)
                self._rebuild_right_panel()

    def delete_prompt(self, name):
        if "PROMPTS" in config.conf and name in config.conf["PROMPTS"]:
            del config.conf["PROMPTS"][name]
            save_config(config.conf)
            self._rebuild_right_panel()

    def _build_profile_panel(self):
        self._add_panel_header(tr("tab_profile"), self.save_profile)

        avatar_row = QHBoxLayout()
        self.profile_avatar = QLabel()
        self.profile_avatar.setFixedSize(80, 80)
        self.profile_avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.profile_avatar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.profile_avatar.mousePressEvent = self.change_profile_avatar_click
        avatar_row.addWidget(self.profile_avatar)
        avatar_row.addStretch()
        self.right_layout.addLayout(avatar_row)
        self._refresh_profile_avatar()

        self.profile_name_input = QLineEdit()
        self.profile_name_input.setPlaceholderText(tr("profile_name"))
        self.profile_name_input.setStyleSheet(self._input_style())

        self.profile_age_input = QLineEdit()
        self.profile_age_input.setPlaceholderText(tr("profile_age"))
        self.profile_age_input.setStyleSheet(self._input_style())

        self.profile_about_input = QTextEdit()
        self.profile_about_input.setPlaceholderText(tr("profile_about"))
        self.profile_about_input.setStyleSheet(self._input_style())
        self.profile_about_input.setFixedHeight(160)

        for label, widget in [
            (tr("profile_name"), self.profile_name_input),
            (tr("profile_age"), self.profile_age_input),
            (tr("profile_about"), self.profile_about_input),
        ]:
            lbl = QLabel(label)
            lbl.setStyleSheet(self._label_style())
            self.right_layout.addWidget(lbl)
            self.right_layout.addWidget(widget)

        self.right_layout.addStretch(1)

    def _build_chat_messages_panel(self):
        row = QHBoxLayout()
        title_text = self.active_chat_name
        if len(title_text) > 30:
            title_text = title_text[:30] + "..."
        self.chat_title_lbl = QLabel(title_text)
        self.chat_title_lbl.setStyleSheet(self._title_style(20))
        row.addWidget(self.chat_title_lbl)
        row.addStretch()
        self.chat_gear_btn = QPushButton("⚙")
        self.chat_gear_btn.setFixedSize(40, 40)
        self.chat_gear_btn.setStyleSheet(
            f"color: {self.t['accent']}; background: transparent; border: none; "
            f"font-size: 22px;"
        )
        self.chat_gear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.chat_gear_btn.clicked.connect(self.open_chat_settings)
        row.addWidget(self.chat_gear_btn)
        self.right_layout.addLayout(row)

        self.messages_view = ChatMessagesView()
        self.right_layout.addWidget(self.messages_view, 1)
        cached = self._messages_cache.get(self.active_chat_id)
        if cached:
            self.messages_view.set_messages(cached)
        self._load_chat_messages()

    def _build_chat_settings_panel(self):
        row = QHBoxLayout()
        back_btn = self._make_outline_button(tr("back_to_messages"))
        back_btn.clicked.connect(self.back_to_chat_messages)
        row.addWidget(back_btn)
        row.addStretch()
        title = QLabel(tr("chat_settings"))
        title.setStyleSheet(self._label_style(16, muted=True))
        row.addWidget(title)
        self.right_layout.addLayout(row)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            f"border: none; background: {self.t['panel']};"
        )
        content = QWidget()
        content.setStyleSheet(f"background: {self.t['panel']};")
        layout = QVBoxLayout(content)
        layout.setSpacing(14)

        prompt_lbl = QLabel(tr("select_prompt"))
        prompt_lbl.setStyleSheet(self._label_style())
        layout.addWidget(prompt_lbl)

        prompts_dict = config.conf.get("PROMPTS", {})
        if not prompts_dict:
            err_lbl = QLabel(tr("error_no_prompts"))
            err_lbl.setStyleSheet("color: #ff3b30; font-size: 13px; font-weight: bold;")
            layout.addWidget(err_lbl)
            self.chat_prompt_combo = None
        else:
            self.chat_prompt_combo = QComboBox()
            self.chat_prompt_combo.setView(QListView())
            self.chat_prompt_combo.setStyleSheet(self._combo_style())
            for name in prompts_dict.keys():
                self.chat_prompt_combo.addItem(name, name)
            self.chat_prompt_combo.currentIndexChanged.connect(self.save_chat_prompt)
            layout.addWidget(self.chat_prompt_combo)

        style_lbl = QLabel(tr("change_style"))
        style_lbl.setStyleSheet(self._label_style())
        layout.addWidget(style_lbl)

        style_row = QHBoxLayout()
        self.formal_btn = QPushButton(tr("formal_style"))
        self.casual_btn = QPushButton(tr("casual_style"))
        self.formal_btn.clicked.connect(lambda: self.set_chat_style("formal"))
        self.casual_btn.clicked.connect(lambda: self.set_chat_style("casual"))
        style_row.addWidget(self.formal_btn)
        style_row.addWidget(self.casual_btn)
        layout.addLayout(style_row)

        for label, slot in [
            (tr("write_first"), self.action_write_first),
            (tr("sync_chat"), self.action_sync_chat),
            (tr("delete_chat"), self.action_delete_chat),
        ]:
            b = QPushButton(label)
            if label == tr("delete_chat"):
                b.setStyleSheet(
                    "background-color: #aa3333; color: white; border: none; "
                    "border-radius: 12px; font-weight: bold; padding: 10px;"
                )
                b.clicked.connect(slot)
            else:
                b.setStyleSheet(self._btn_grey_style())
                self._connect_action_with_press(b, slot)
            layout.addWidget(b)

        sum_lbl = QLabel(tr("summary"))
        sum_lbl.setStyleSheet(self._label_style())
        layout.addWidget(sum_lbl)

        sum_row = QHBoxLayout()
        self.date_input = QLineEdit()
        self.date_input.setPlaceholderText("DDMM")
        self.date_input.setStyleSheet(self._input_style())
        self.date_input.setFixedWidth(100)
        gen_btn = QPushButton(tr("summary"))
        gen_btn.setStyleSheet(self._btn_grey_style())
        self._connect_action_with_press(gen_btn, self.action_get_summary)
        sum_row.addWidget(self.date_input)
        sum_row.addWidget(gen_btn)
        layout.addLayout(sum_row)

        self.summary_text = QTextEdit()
        self.summary_text.setReadOnly(True)
        self.summary_text.setPlaceholderText(tr("summary_placeholder"))
        self.summary_text.setStyleSheet(self._messages_box_style())
        self.summary_text.setFixedHeight(200)
        layout.addWidget(self.summary_text)

        layout.addStretch()
        scroll.setWidget(content)
        self.right_layout.addWidget(scroll, 1)
        self._apply_chat_settings_from_db()

    def _refresh_profile_avatar(self):
        if not self._is_alive(getattr(self, "profile_avatar", None)):
            return
        t = palette()
        user_id = get_my_user_id()
        self.profile_avatar.setStyleSheet(
            f"background-color: {t['avatar_bg']}; border-radius: 40px; border: none;"
        )
        path = avatar_file(user_id) if user_id else default_avatar_path()
        if path:
            from PyQt6.QtGui import QPixmap

            pixmap = QPixmap(str(path))
            if not pixmap.isNull():
                self.profile_avatar.setPixmap(
                    rounded_pixmap(pixmap, size=80, radius=40)
                )
                return
        self.profile_avatar.clear()

    def change_profile_avatar_click(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            from PyQt6.QtWidgets import QFileDialog
            import shutil
            from core.avatars import ensure_assets_dir, avatar_save_path
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                tr("select_avatar"),
                "",
                "Images (*.png *.jpg *.jpeg)",
            )
            if file_path:
                try:
                    ensure_assets_dir()
                    shutil.copy(file_path, config.IMAGE_PATH)
                    my_id = get_my_user_id()
                    if my_id:
                        shutil.copy(file_path, avatar_save_path(my_id))
                    self._refresh_profile_avatar()
                except Exception as e:
                    self.show_error(str(e))

    def _load_profile_fields(self):
        self._profile_load_gen += 1
        load_gen = self._profile_load_gen

        async def load():
            try:
                if not database.db:
                    database.db = await init_db()
                await resolve_my_user_id()
                profile = await get_app_profile()
                if load_gen != self._profile_load_gen:
                    return
                signals.profile_loaded.emit(
                    profile["display_name"],
                    profile["age"],
                    profile["about"],
                )
            except Exception as exc:
                pass

        loop = telegram_bot.loop
        if loop is None:
            return
        try:
            asyncio.run_coroutine_threadsafe(load(), loop)
        except Exception as exc:
            pass

    def _on_profile_loaded(self, name, age, about):
        self._refresh_profile_avatar()
        if not self._is_alive(getattr(self, "profile_name_input", None)):
            return
        try:
            self.profile_name_input.setText(name or "")
            self.profile_age_input.setText(age or "")
            self.profile_about_input.setPlainText(about or "")
        except Exception as exc:
            pass

    def save_profile(self):
        async def save():
            if not database.db:
                database.db = await init_db()
            await save_app_profile(
                self.profile_name_input.text().strip(),
                self.profile_age_input.text().strip(),
                self.profile_about_input.toPlainText().strip(),
            )

        asyncio.run_coroutine_threadsafe(save(), telegram_bot.loop)

    def save_settings(self):
        try:
            if hasattr(self, "api_id_input") and self.api_id_input:
                try:
                    config.conf["API_ID"] = int(self.api_id_input.text())
                except ValueError:
                    pass
            if hasattr(self, "api_hash_input") and self.api_hash_input:
                config.conf["API_HASH"] = self.api_hash_input.text().strip()
            if hasattr(self, "key_input") and self.key_input:
                config.conf["API_KEY"] = self.key_input.text().strip()
            if hasattr(self, "timezone_combo") and self.timezone_combo:
                config.conf["TIMEZONE"] = int(self.timezone_combo.currentData())
            if hasattr(self, "api_combo") and self.api_combo:
                selected_api = self.api_combo.currentData()
                config.conf["SELECTED_API"] = selected_api

                async def save_to_db():
                    if not database.db:
                        database.db = await database.init_db()
                    await database.db.execute(
                        "UPDATE app_profile SET selected_api=? WHERE id=1",
                        (selected_api,),
                    )
                    await database.db.commit()

                asyncio.run_coroutine_threadsafe(save_to_db(), telegram_bot.loop)

            if hasattr(self, "_prompt_edits") and self._prompt_edits:
                for name, text_edit in self._prompt_edits.items():
                    if text_edit:
                        config.conf["PROMPTS"][name] = text_edit.toPlainText()

            save_config(config.conf)

            if self.active_chat_id and self._is_alive(
                getattr(self, "messages_view", None)
            ):
                self._messages_cache.pop(self.active_chat_id, None)
                self._load_chat_messages()
        except Exception:
            pass

    def toggle_ui_language(self):
        current = config.conf.get("LANGUAGE", "en")
        config.conf["LANGUAGE"] = "ru" if current == "en" else "en"
        save_config(config.conf)
        if hasattr(self, "lang_toggle_btn"):
            self.lang_toggle_btn.setText(
                language_label(config.conf.get("LANGUAGE", "en"))
            )
        self.update_ui_language()
        self.refresh_chats()
        if self.split_visible:
            self._rebuild_right_panel()

    def update_ui_language(self):
        self._apply_conn_button_style()
        self.tab_chats_btn.setText(tr("tab_chats"))
        self.tab_settings_btn.setText(tr("tab_settings"))
        self.tab_profile_btn.setText(tr("tab_profile"))
        self.chats_title.setText(tr("tab_chats"))
        self.new_chat_btn.setText(tr("new_chat"))

    def update_style_buttons(self, style):
        if not hasattr(self, "formal_btn"):
            return
        style = (style or "formal").strip().lower()
        base = self._btn_grey_style()
        active = self._btn_outline_style()
        self.formal_btn.setStyleSheet(active if style == "formal" else base)
        self.casual_btn.setStyleSheet(active if style == "casual" else base)

    def _on_chat_settings_ready(self, mode, style, selected_prompt):
        if self.right_mode != "chat" or self.chat_subview != "settings":
            return
        if self.active_chat_id is None:
            return
        self.update_style_buttons(style)

        if hasattr(self, "chat_prompt_combo") and self.chat_prompt_combo:
            self.chat_prompt_combo.blockSignals(True)
            prompts = config.conf.get("PROMPTS", {})
            prompt_names = list(prompts.keys())
            
            if not selected_prompt and 0 <= mode < len(prompt_names):
                selected_prompt = prompt_names[mode]
                
            idx = self.chat_prompt_combo.findData(selected_prompt)
            if idx >= 0:
                self.chat_prompt_combo.setCurrentIndex(idx)
            elif self.chat_prompt_combo.count() > 0:
                self.chat_prompt_combo.setCurrentIndex(0)
                
            self.chat_prompt_combo.blockSignals(False)

    def _apply_chat_settings_from_db(self):
        chat_id = self.active_chat_id

        async def load():
            if not database.db:
                database.db = await init_db()

            async with database.db.execute(
                "SELECT bot_mode, communication_style, selected_prompt FROM profiles WHERE user_id=?",
                (chat_id,),
            ) as cur:
                row = await cur.fetchone()

            mode = int(row[0]) if row and row[0] is not None else 0
            style = (
                str(row[1]).strip().lower() if row and row[1] else "formal"
            )
            selected_prompt = str(row[2]) if row and len(row) > 2 and row[2] else ""
            signals.chat_settings_ready.emit(mode, style, selected_prompt)

        asyncio.run_coroutine_threadsafe(load(), telegram_bot.loop)

    def _on_avatar_updated(self, user_id):
        item = self.chat_items.get(user_id)
        if item:
            item.refresh_avatar()
        my_id = get_my_user_id()
        if my_id and user_id == my_id:
            self._refresh_profile_avatar()

    def set_chat_style(self, style):
        async def update():
            await database.db.execute(
                "UPDATE profiles SET communication_style=? WHERE user_id=?",
                (style, self.active_chat_id),
            )
            await database.db.commit()

        asyncio.run_coroutine_threadsafe(update(), telegram_bot.loop)
        self.update_style_buttons(style)

    def save_chat_prompt(self):
        if not hasattr(self, "chat_prompt_combo") or not self.chat_prompt_combo:
            return
        selected_prompt = self.chat_prompt_combo.currentData()
        chat_id = self.active_chat_id
        if not chat_id or not selected_prompt:
            return

        async def update():
            prompts = config.conf.get("PROMPTS", {})
            prompt_names = list(prompts.keys())
            try:
                mode_idx = prompt_names.index(selected_prompt)
            except ValueError:
                mode_idx = 0

            await database.db.execute(
                "UPDATE profiles SET selected_prompt=?, bot_mode=? WHERE user_id=?",
                (selected_prompt, mode_idx, chat_id),
            )
            await database.db.commit()

        asyncio.run_coroutine_threadsafe(update(), telegram_bot.loop)

    def _load_chat_messages(self):
        chat_id = self.active_chat_id
        if chat_id is None:
            return

        async def load():
            try:
                if not database.db:
                    database.db = await init_db()
                async with database.db.execute(
                    "SELECT text, sender_id, timestamp FROM messages "
                    "WHERE chat_id=? ORDER BY timestamp ASC LIMIT 300",
                    (chat_id,),
                ) as cur:
                    rows = await cur.fetchall()

                parsed = []
                for text, sender_id, ts in rows:
                    if not text:
                        continue
                    try:
                        is_mine = int(sender_id or 0) == 0
                        time_str = format_message_time_local(ts)
                        parsed.append([str(text), is_mine, time_str])
                    except Exception:
                        parsed.append([str(text), int(sender_id or 0) == 0, ""])

                signals.messages_loaded.emit(chat_id, parsed)
            except Exception:
                if chat_id not in self._messages_cache:
                    signals.messages_loaded.emit(chat_id, [])

        loop = telegram_bot.loop
        if loop is None:
            QTimer.singleShot(0, lambda: self._on_messages_loaded(chat_id, []))
            return
        try:
            asyncio.run_coroutine_threadsafe(load(), loop)
        except Exception:
            QTimer.singleShot(0, lambda: self._on_messages_loaded(chat_id, []))

    def _on_messages_loaded(self, chat_id, rows):
        self._messages_cache[chat_id] = rows
        if chat_id != self.active_chat_id:
            return
        mv = getattr(self, "messages_view", None)
        if not self._is_alive(mv):
            return
        try:
            mv.set_messages(rows)
        except Exception:
            pass

    def show_error(self, text):
        self.error_label.setText(text)
        self.error_label.show()
        QTimer.singleShot(3000, self.error_label.hide)

    def set_summary_text_safe(self, text):
        if hasattr(self, "summary_text"):
            self.summary_text.setText(text)

    def action_write_first(self):
        if not self.is_running or not telegram_bot.client:
            return

        async def run():
            try:
                prompt_type = await database.get_prompt_for_chat(self.active_chat_id)
                bio = await get_profile_bio_text()
                prompt = f"{bio}\n{prompt_type}\nНапиши первое сообщение для начала диалога."
                text = await call_groq_api(prompt)
                await telegram_bot.client.send_message(self.active_chat_id, text)
                await database.db.execute(
                    "INSERT INTO messages (chat_id, sender_id, text, timestamp) "
                    "VALUES (?, ?, ?, ?)",
                    (
                        self.active_chat_id,
                        0,
                        text,
                        store_message_timestamp(None),
                    ),
                )
                await database.db.commit()
                signals.update_summary_signal.emit(tr("message_sent"))
                self._load_chat_messages()
            except Exception as e:
                signals.update_summary_signal.emit(f"Error: {e}")

        asyncio.run_coroutine_threadsafe(run(), telegram_bot.loop)

    def action_delete_chat(self):
        chat_id = self.active_chat_id

        async def run():
            await database.db.execute(
                "DELETE FROM profiles WHERE user_id=?",
                (chat_id,),
            )
            await database.db.execute(
                "DELETE FROM messages WHERE chat_id=?",
                (chat_id,),
            )
            await database.db.commit()
            delete_avatar(chat_id)
            self.active_chat_id = None
            self.chat_subview = "messages"
            self.hide_split()
            signals.chat_list_updated.emit()

        asyncio.run_coroutine_threadsafe(run(), telegram_bot.loop)

    def action_sync_chat(self):
        if not self.is_running:
            return

        async def run():
            try:
                entity = await telegram_bot.client.get_entity(self.active_chat_id)
                async for msg in telegram_bot.client.iter_messages(entity, limit=100):
                    if not msg.text:
                        continue
                    sender_id = 0 if msg.out else (msg.sender_id or self.active_chat_id)
                    await database.db.execute(
                        "INSERT OR IGNORE INTO messages "
                        "(chat_id, sender_id, text, timestamp, tg_msg_id) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (
                            self.active_chat_id,
                            sender_id,
                            msg.text,
                            store_message_timestamp(msg.date),
                            msg.id,
                        ),
                    )
                await database.db.commit()
                self._messages_cache.pop(self.active_chat_id, None)
                self._load_chat_messages()
                signals.update_summary_signal.emit(
                    "Sync complete."
                    if config.conf.get("LANGUAGE") == "en"
                    else "Синхронизация завершена."
                )
            except Exception as e:
                signals.update_summary_signal.emit(f"Error: {e}")

        asyncio.run_coroutine_threadsafe(run(), telegram_bot.loop)

    def action_get_summary(self):
        if not hasattr(self, "date_input"):
            return
        date_str = self.date_input.text()
        if len(date_str) != 4:
            return

        signals.update_summary_signal.emit(tr("retelling_generation"))

        async def run():
            try:
                day = date_str[:2]
                month = date_str[2:]
                target = f"{datetime.now().year}-{month}-{day}%"
                async with database.db.execute(
                    "SELECT text FROM messages WHERE chat_id=? "
                    "AND timestamp LIKE ? LIMIT 100",
                    (self.active_chat_id, target),
                ) as cur:
                    rows = await cur.fetchall()
                    history = "\n".join([r[0] for r in rows if r[0]])
                    if not history:
                        signals.update_summary_signal.emit(tr("no_messages"))
                        return
                    ai_summary = await generate_ai_summary(history)
                    header = f"{tr('summary_for')} {day}.{month} ({len(rows)} msgs):\n\n"
                    signals.update_summary_signal.emit(header + ai_summary)
            except Exception as e:
                signals.update_summary_signal.emit(f"Error: {str(e)}")

        asyncio.run_coroutine_threadsafe(run(), telegram_bot.loop)

    def prompt_add_chat(self):
        if not self.is_running or not telegram_bot.client:
            self.show_error(tr("connect_first"))
            return

        dlg = AddChatDialog(self)
        from PyQt6.QtWidgets import QDialog

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        username = dlg.get_username()
        if not username:
            return

        async def add():
            try:
                try:
                    entity_input = int(username)
                except ValueError:
                    entity_input = username

                u = await telegram_bot.client.get_entity(entity_input)
                from telethon.utils import get_display_name
                name = get_display_name(u) or "Unknown"
                await database.db.execute(
                    """
                    INSERT OR IGNORE INTO profiles
                    (user_id, username, name, status, is_me, communication_style, bot_mode)
                    VALUES (?, ?, ?, 'active', 0, 'formal', 0)
                    """,
                    (
                        u.id,
                        getattr(u, "username", "") or "",
                        name,
                    ),
                )
                await database.db.execute(
                    """
                    UPDATE profiles SET username=?, name=?, status='active'
                    WHERE user_id=?
                    """,
                    (
                        getattr(u, "username", "") or "",
                        name,
                        u.id,
                    ),
                )
                await database.db.commit()
                try:
                    await download_chat_avatar(u.id)
                except Exception:
                    pass
                signals.avatar_updated.emit(u.id)
                signals.chat_list_updated.emit()
                QTimer.singleShot(
                    100,
                    lambda: self.select_chat(u.id, name),
                )
            except Exception as e:
                signals.error_signal.emit(f"ADD_CHAT_FAIL: {e}")

        asyncio.run_coroutine_threadsafe(add(), telegram_bot.loop)

    def refresh_chats(self):
        async def fetch():
            if not database.db:
                database.db = await init_db()
            async with database.db.execute(
                "SELECT user_id, name, status FROM profiles "
                "WHERE is_me=0 ORDER BY user_id DESC"
            ) as cur:
                users = await cur.fetchall()
                signals.data_loaded.emit(users)

            if telegram_bot.client and telegram_bot.client.is_connected():
                for user_id, _, _ in users:
                    if not has_user_avatar(user_id):
                        try:
                            await download_chat_avatar(user_id)
                        except Exception:
                            pass
                    signals.avatar_updated.emit(user_id)

        asyncio.run_coroutine_threadsafe(fetch(), telegram_bot.loop)

    def _update_chat_list_frame_size(self):
        if not hasattr(self, "chat_list_frame"):
            return
        n = len(self.chat_items)
        if n == 0:
            self.chat_list_frame.setFixedHeight(0)
            return
        h = n * 64 + max(0, n - 1)
        self.chat_list_frame.setFixedHeight(h)

    def render_chat_list(self, users):
        self._last_users = users
        self.clear_layout(self.chat_layout)
        self.chat_items.clear()

        for idx, u in enumerate(users):
            item = ChatItem(
                u[0],
                u[1],
                u[2],
                parent_app=self,
                selected=(u[0] == self.active_chat_id),
            )
            self.chat_items[u[0]] = item
            self.chat_layout.addWidget(item)

            if idx < len(users) - 1:
                sep = QFrame()
                sep.setFixedHeight(1)
                sep.setStyleSheet(self._chat_list_separator_style())
                self.chat_layout.addWidget(sep)

        self._update_chat_list_frame_size()
        QTimer.singleShot(0, self._update_chat_list_frame_size)

    def refresh_chat_items_theme(self):
        for item in self.chat_items.values():
            if hasattr(item, "refresh_theme"):
                item.refresh_theme()

    def update_bot_status_ui(self, running):
        self.is_running = running
        self.status_lbl.setText("online" if running else "offline")
        self.status_lbl.setStyleSheet(
            f"color: {self.t['accent'] if running else self.t['muted']}; "
            f"font-size: 13px; font-weight: bold; border: none; outline: none; "
            f"background: transparent; padding: 0px;"
        )
        self._apply_conn_button_style()
        if running:
            self.refresh_chats()

    def toggle_bot(self):
        self.animate_button_press(self.conn_btn)
        if not self.is_running:
            asyncio.run_coroutine_threadsafe(start_client(), telegram_bot.loop)
        else:
            asyncio.run_coroutine_threadsafe(stop_client(), telegram_bot.loop)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "main_frame"):
            apply_rounded_mask(self.main_frame, WIN_RADIUS)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.window_drag_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if self.window_drag_pos:
            delta = event.globalPosition().toPoint() - self.window_drag_pos
            self.move(self.pos() + delta)
            self.window_drag_pos = event.globalPosition().toPoint()
