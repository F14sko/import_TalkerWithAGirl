import asyncio

from PyQt6.QtCore import Qt, pyqtSignal, QObject, QTimer, QRectF
from PyQt6.QtGui import QPixmap, QPainter, QPainterPath, QRegion
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QLineEdit,
    QDialog,
    QInputDialog,
    QSizePolicy,
    QDialogButtonBox,
    QWidget,
    QTextEdit,
)
from telethon.sync import TelegramClient as SyncTelegramClient

from core import config
from core import database
from core.avatars import avatar_file
from core.config import load_config, reload_config, save_config
from core.theme import palette


def _event_loop():
    from core import telegram_bot
    return telegram_bot.loop


class BotSignals(QObject):
    status_changed = pyqtSignal(bool)
    chat_list_updated = pyqtSignal()
    data_loaded = pyqtSignal(list)
    update_summary_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)
    chat_settings_ready = pyqtSignal(int, str, str)
    avatar_updated = pyqtSignal(int)
    messages_loaded = pyqtSignal(int, object)
    profile_loaded = pyqtSignal(str, str, str)
    theme_changed = pyqtSignal()


signals = BotSignals()

AVATAR_SIZE = 44
AVATAR_RADIUS = 22
MESSAGES_PANEL_RADIUS = 14


def apply_rounded_mask(widget, radius):
    path = QPainterPath()
    path.addRoundedRect(QRectF(widget.rect()), radius, radius)
    widget.setMask(QRegion(path.toFillPolygon().toPolygon()))


def rounded_pixmap(source: QPixmap, size=AVATAR_SIZE, radius=AVATAR_RADIUS):
    scaled = source.scaled(
        size,
        size,
        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
        Qt.TransformationMode.SmoothTransformation,
    )
    result = QPixmap(size, size)
    result.fill(Qt.GlobalColor.transparent)

    painter = QPainter(result)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    path = QPainterPath()
    path.addRoundedRect(0, 0, size, size, radius, radius)
    painter.setClipPath(path)
    painter.drawPixmap(0, 0, scaled)
    painter.end()

    return result


def _toggle_on_style():
    t = palette()
    return (
        f"background-color: {t['accent']}; color: white; border: none; "
        f"border-radius: 15px; font-weight: bold; font-size: 12px;"
    )


def _toggle_off_style():
    t = palette()
    acc = t["accent"]
    return (
        f"background-color: transparent; color: {acc}; "
        f"border: 2px solid {acc}; border-radius: 15px; font-weight: bold; "
        f"font-size: 12px; padding: 2px 6px;"
    )


def _add_chat_dialog_stylesheet():
    t = palette()
    acc = t["accent"]
    return (
        f"QDialog {{ background-color: {t['panel']}; color: {t['text']}; }}"
        f"QLabel {{ color: {t['muted']}; font-size: 13px; background: transparent; }}"
        f"QLineEdit {{ background: {t['input_bg']}; color: {t['input_text']}; "
        f"border: none; border-radius: 10px; padding: 10px; font-size: 14px; }}"
        f"QPushButton {{ color: {acc}; background: transparent; "
        f"border: 2px solid {acc}; border-radius: 10px; padding: 8px 16px; "
        f"font-size: 14px; }}"
        f"QPushButton:hover {{ background-color: {t['selected_bg']}; }}"
    )


class AddChatDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        from core.config import tr

        self.added_user_id = None
        self.added_name = None

        self.setWindowTitle(tr("add_chat"))
        self.setFixedSize(400, 180)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(_add_chat_dialog_stylesheet())

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        hint = QLabel(tr("add_chat_hint"))
        layout.addWidget(hint)

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText(tr("add_chat_placeholder"))
        layout.addWidget(self.username_input)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(tr("add"))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(
            tr("back")
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_username(self):
        return self.username_input.text().replace("@", "").strip()


class AddPromptDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        from core.config import tr

        self.setWindowTitle(tr("add_prompt_title"))
        self.setFixedSize(400, 320)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(_add_chat_dialog_stylesheet())

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        name_lbl = QLabel(tr("prompt_name_label"))
        layout.addWidget(name_lbl)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText(tr("prompt_name_placeholder"))
        layout.addWidget(self.name_input)

        text_lbl = QLabel(tr("prompt_text_label"))
        layout.addWidget(text_lbl)

        self.text_input = QTextEdit()
        self.text_input.setPlaceholderText(tr("prompt_text_placeholder"))
        self.text_input.setStyleSheet(
            f"background: {palette()['input_bg']}; color: {palette()['input_text']}; "
            f"border: none; border-radius: 10px; padding: 10px; font-size: 14px;"
        )
        layout.addWidget(self.text_input)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(tr("add"))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(
            tr("back")
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_data(self):
        return self.name_input.text().strip(), self.text_input.toPlainText().strip()


def _normalize_message_rows(rows):
    parsed = []
    for row in rows or []:
        if isinstance(row, (list, tuple)) and len(row) >= 2:
            is_mine = row[1]
            if isinstance(is_mine, (int, float)):
                is_mine = int(is_mine) == 0
            else:
                is_mine = bool(is_mine)
            parsed.append(
                (str(row[0] or ""), is_mine, str(row[2] if len(row) > 2 else ""))
            )
    return parsed


class MessageBubble(QWidget):
    def __init__(self, text, is_mine, time_str=""):
        super().__init__()
        self._is_mine = is_mine
        self._text = str(text or "")
        self._time_str = time_str
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Minimum,
        )
        self._build()

    def _bubble_colors(self):
        t = palette()
        if self._is_mine:
            return t["bubble_mine_bg"], t["bubble_mine_text"]
        return t["bubble_peer_bg"], t["bubble_peer_text"]

    def _make_bubble_frame(self):
        bg, fg = self._bubble_colors()
        frame = QFrame()
        frame.setMaximumWidth(340)
        frame.setSizePolicy(
            QSizePolicy.Policy.Maximum,
            QSizePolicy.Policy.Minimum,
        )
        frame.setStyleSheet(
            f"QFrame {{ background-color: {bg}; border-radius: 16px; border: none; }}"
        )
        inner = QVBoxLayout(frame)
        inner.setContentsMargins(14, 12, 14, 12)
        inner.setSpacing(0)

        label = QLabel(self._text)
        label.setWordWrap(True)
        label.setStyleSheet(
            f"color: {fg}; font-size: 13px; background: transparent; border: none;"
        )
        label.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Minimum,
        )
        inner.addWidget(label)
        return frame

    def _build(self):
        if self.layout():
            while self.layout().count():
                item = self.layout().takeAt(0)
                w = item.widget()
                if w:
                    w.deleteLater()

        t = palette()
        row = QHBoxLayout(self)
        row.setContentsMargins(8, 2, 8, 2)
        row.setSpacing(0)

        text_align = (
            Qt.AlignmentFlag.AlignRight
            if self._is_mine
            else Qt.AlignmentFlag.AlignLeft
        )

        col = QVBoxLayout()
        col.setSpacing(2)
        col.setContentsMargins(0, 0, 0, 0)
        col.addWidget(self._make_bubble_frame(), 0, text_align)

        if self._time_str:
            time_lbl = QLabel(self._time_str)
            time_lbl.setSizePolicy(
                QSizePolicy.Policy.Maximum,
                QSizePolicy.Policy.Preferred,
            )
            time_lbl.setStyleSheet(
                f"color: {t['muted']}; font-size: 10px; padding: 0 8px; "
                f"border: none; outline: none; background: transparent;"
            )
            col.addWidget(time_lbl, 0, text_align)

        wrap = QWidget()
        wrap.setLayout(col)
        wrap.setSizePolicy(
            QSizePolicy.Policy.Maximum,
            QSizePolicy.Policy.Minimum,
        )

        if self._is_mine:
            row.addWidget(wrap)
            row.addStretch(1)
        else:
            row.addStretch(1)
            row.addWidget(wrap)

    def refresh_theme(self):
        self._build()


class ChatMessagesView(QScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("messagesView")
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._content = QWidget()
        self._layout = QVBoxLayout(self._content)
        self._layout.setSpacing(6)
        self._layout.setContentsMargins(12, 12, 12, 12)
        self._layout.addStretch()
        self.setWidget(self._content)
        self.apply_theme_style()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        apply_rounded_mask(self, MESSAGES_PANEL_RADIUS)

    def apply_theme_style(self):
        t = palette()
        bg = t["messages_bg"]
        border = t["scrollbar_handle"]
        handle = t["scrollbar_handle"]
        r = MESSAGES_PANEL_RADIUS
        self.setStyleSheet(
            f"QScrollArea#messagesView {{"
            f" background-color: {bg};"
            f" border: 1px solid {border};"
            f" border-radius: {r}px;"
            f"}}"
            f"QScrollArea#messagesView QWidget#qt_scrollarea_viewport {{"
            f" background-color: {bg}; border: none;"
            f"}}"
            f"QScrollArea#messagesView QScrollBar:vertical {{"
            f" width: 0px; background: transparent;"
            f"}}"
            f"QScrollArea#messagesView QScrollBar::handle:vertical {{"
            f" background: transparent;"
            f"}}"
            f"QScrollArea#messagesView QScrollBar::add-line:vertical,"
            f" QScrollArea#messagesView QScrollBar::sub-line:vertical {{"
            f" height: 0px; border: none; background: transparent;"
            f"}}"
            f"QScrollArea#messagesView QScrollBar::add-page:vertical,"
            f" QScrollArea#messagesView QScrollBar::sub-page:vertical {{"
            f" background: transparent;"
            f"}}"
        )
        self.viewport().setStyleSheet(
            f"background-color: {bg}; border: none;"
        )
        self._content.setStyleSheet(f"background-color: {bg}; border: none;")
        QTimer.singleShot(0, lambda: apply_rounded_mask(self, MESSAGES_PANEL_RADIUS))

    def clear_messages(self):
        while self._layout.count() > 1:
            item = self._layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def set_messages(self, rows):
        rows = _normalize_message_rows(rows)
        self.clear_messages()
        if not rows:
            t = palette()
            empty = QLabel("—")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet(
                f"color: {t['muted']}; font-size: 14px; padding: 24px;"
            )
            self._layout.insertWidget(0, empty)
        else:
            for text, is_mine, time_str in rows:
                self._layout.insertWidget(
                    self._layout.count() - 1,
                    MessageBubble(text, is_mine, time_str),
                )
        QTimer.singleShot(50, self._scroll_bottom)

    def _scroll_bottom(self):
        bar = self.verticalScrollBar()
        bar.setValue(bar.maximum())


class RestrictedScrollArea(QScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_scroll_allowed = True

    def wheelEvent(self, event):
        if self.is_scroll_allowed:
            super().wheelEvent(event)
        else:
            event.ignore()


class TelegramLoginDialog(QDialog):
    def __init__(self):
        super().__init__()

        self.phone = ""
        self.code = ""
        self.sync_client = None
        self.old_pos = None

        cfg = load_config()

        self.setWindowTitle("Telegram Авторизация")
        self.setFixedSize(340, 320)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self.main_frame = QFrame(self)
        self.main_frame.setGeometry(0, 0, 340, 320)
        self.main_frame.setStyleSheet(
            "background-color: #1a1a1a; border-radius: 0px;"
        )

        title = QLabel("Telegram Login", self.main_frame)
        title.setGeometry(0, 20, 340, 40)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            "color: white; font-size: 24px; font-weight: bold;"
        )

        self.close_btn = QPushButton("✕", self.main_frame)
        self.close_btn.setGeometry(295, 15, 30, 30)
        self.close_btn.setStyleSheet(
            "color: #ff9800; border: none; font-size: 18px; font-weight: bold;"
        )
        self.close_btn.clicked.connect(self.reject)

        self.api_id_input = QLineEdit(self.main_frame)
        self.api_id_input.setPlaceholderText("API_ID")
        api_id = cfg.get("API_ID", "")
        self.api_id_input.setText("" if api_id == 0 else str(api_id))
        self.api_id_input.setGeometry(30, 75, 280, 40)
        self.api_id_input.setStyleSheet("""
            background: #333;
            color: white;
            border: none;
            border-radius: 14px;
            padding-left: 15px;
            font-size: 14px;
        """)

        self.api_hash_input = QLineEdit(self.main_frame)
        self.api_hash_input.setPlaceholderText("API_HASH")
        self.api_hash_input.setText(cfg.get("API_HASH", ""))
        self.api_hash_input.setGeometry(30, 125, 280, 40)
        self.api_hash_input.setStyleSheet("""
            background: #333;
            color: white;
            border: none;
            border-radius: 14px;
            padding-left: 15px;
            font-size: 14px;
        """)

        self.phone_input = QLineEdit(self.main_frame)
        self.phone_input.setPlaceholderText("Phone number")
        self.phone_input.setGeometry(30, 175, 280, 42)
        self.phone_input.setStyleSheet("""
            background: #333;
            color: white;
            border: none;
            border-radius: 14px;
            padding-left: 15px;
            font-size: 15px;
        """)

        self.send_code_btn = QPushButton("Send Code", self.main_frame)
        self.send_code_btn.setGeometry(30, 225, 280, 42)
        self.send_code_btn.setStyleSheet("""
            background-color: #ff9800;
            color: white;
            border-radius: 14px;
            font-size: 15px;
            font-weight: bold;
            border: none;
        """)

        self.code_input = QLineEdit(self.main_frame)
        self.code_input.setPlaceholderText("Code from Telegram")
        self.code_input.setGeometry(30, 175, 280, 42)
        self.code_input.setStyleSheet("""
            background: #333;
            color: white;
            border: none;
            border-radius: 14px;
            padding-left: 15px;
            font-size: 15px;
        """)
        self.code_input.hide()

        self.login_btn = QPushButton("Login", self.main_frame)
        self.login_btn.setGeometry(30, 225, 280, 42)
        self.login_btn.setStyleSheet("""
            background-color: #ff9800;
            color: white;
            border-radius: 16px;
            font-size: 15px;
            font-weight: bold;
            border: none;
        """)
        self.login_btn.hide()

        self.send_code_btn.clicked.connect(self.send_code)
        self.login_btn.clicked.connect(self.finish_login)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.old_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if self.old_pos:
            delta = event.globalPosition().toPoint() - self.old_pos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        self.old_pos = None

    def send_code(self):
        self.phone = self.phone_input.text().strip()
        if not self.phone:
            return

        try:
            api_id = int(self.api_id_input.text().strip())
            api_hash = self.api_hash_input.text().strip()

            if not api_id or not api_hash:
                return

            self.sync_client = SyncTelegramClient(
                config.SESSION_STEM,
                api_id,
                api_hash,
            )
            self.sync_client.connect()
            self.sync_client.send_code_request(self.phone)

            self.send_code_btn.hide()
            self.code_input.show()
            self.login_btn.show()

        except Exception:
            pass

    def finish_login(self):
        self.code = self.code_input.text().strip()
        if not self.code:
            return

        try:
            self.sync_client.sign_in(self.phone, self.code)
        except Exception as e:
            if "password" in str(e).lower():
                password, ok = QInputDialog.getText(
                    None,
                    "2FA",
                    "Enter password:",
                    QLineEdit.EchoMode.Password,
                )
                if ok and password:
                    self.sync_client.sign_in(password=password)
                else:
                    return
            else:
                return

        cfg = load_config()
        cfg["API_ID"] = int(self.api_id_input.text().strip())
        cfg["API_HASH"] = self.api_hash_input.text().strip()
        save_config(cfg)
        reload_config()

        self.sync_client.disconnect()
        self.accept()


class ChatItem(QFrame):
    def __init__(
        self,
        user_id,
        name,
        status,
        is_add_button=False,
        parent_app=None,
        selected=False,
    ):
        super().__init__()
        self.user_id = user_id
        self.full_name = name
        self.name = name
        self.bot_status = status
        self.is_add_button = is_add_button
        self.parent_app = parent_app
        self.selected = selected

        if not self.is_add_button:
            limit = 30 if (self.parent_app and self.parent_app.split_visible) else 60
            if len(self.full_name) > limit:
                self.name = self.full_name[:limit] + "..."
            else:
                self.name = self.full_name

        self.initUI()

    def initUI(self):
        t = palette()
        self.setFixedHeight(64)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 12, 0)
        layout.setSpacing(12)

        self.selection_bar = QFrame()
        self.selection_bar.setFixedWidth(4)
        self.selection_bar.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Expanding,
        )
        layout.addWidget(self.selection_bar)

        self.avatar = QLabel()
        self.avatar.setFixedSize(AVATAR_SIZE, AVATAR_SIZE)
        self.avatar.setScaledContents(False)

        if self.is_add_button:
            self.avatar.setStyleSheet(
                f"background-color: {t['avatar_bg']}; border-radius: 22px; "
                f"color: {t['accent']}; font-size: 22px; font-weight: bold;"
            )
            self.avatar.setText("+")
            self.avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        else:
            self.avatar.setStyleSheet(
                f"background-color: {t['avatar_bg']}; border-radius: 22px;"
            )
            self._set_avatar_pixmap()

        layout.addWidget(self.avatar)

        self.name_lbl = QLabel(self.name)
        self.name_lbl.setStyleSheet(
            f"color: {t['text']}; font-size: 15px; font-weight: 500;"
        )
        self.name_lbl.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        layout.addWidget(self.name_lbl)

        if not self.is_add_button:
            self.btn = QPushButton("ON" if self.bot_status == "active" else "OFF")
            self.btn.setFixedSize(56, 30)
            self._apply_toggle_style()
            self.btn.clicked.connect(self._on_toggle_clicked)
            layout.addWidget(self.btn)

        self._apply_selection_style()

    def _set_avatar_pixmap(self):
        path = avatar_file(self.user_id)
        if path:
            pixmap = QPixmap(str(path))
            if not pixmap.isNull():
                self.avatar.setPixmap(rounded_pixmap(pixmap))
                return
        self.avatar.clear()

    def _apply_selection_style(self):
        t = palette()
        if self.is_add_button:
            self.selection_bar.hide()
            self.setStyleSheet("background: transparent; border: none;")
            return
        self.selection_bar.show()
        accent = t["accent"]
        bar_color = accent if self.selected else "transparent"
        self.selection_bar.setStyleSheet(
            f"background-color: {bar_color}; border: none;"
        )
        self.setStyleSheet("background: transparent; border: none;")

    def set_selected(self, selected):
        self.selected = selected
        self._apply_selection_style()

    def refresh_avatar(self):
        if not self.is_add_button:
            self._set_avatar_pixmap()

    def _apply_toggle_style(self):
        if self.bot_status == "active":
            self.btn.setStyleSheet(_toggle_on_style())
        else:
            self.btn.setStyleSheet(_toggle_off_style())

    def _on_toggle_clicked(self):
        self.toggle_status()

    def toggle_status(self):
        new_status = "paused" if self.bot_status == "active" else "active"
        self.bot_status = new_status
        self.btn.setText("ON" if new_status == "active" else "OFF")
        self._apply_toggle_style()

        async def update():
            await database.db.execute(
                "UPDATE profiles SET status=? WHERE user_id=?",
                (new_status, self.user_id),
            )
            await database.db.commit()

        asyncio.run_coroutine_threadsafe(update(), _event_loop())

    def update_name_truncation(self):
        if self.is_add_button:
            return
        limit = 30 if (self.parent_app and self.parent_app.split_visible) else 60
        if len(self.full_name) > limit:
            self.name = self.full_name[:limit] + "..."
        else:
            self.name = self.full_name
        if hasattr(self, "name_lbl") and self.name_lbl:
            self.name_lbl.setText(self.name)

    def refresh_theme(self):
        t = palette()
        if not self.is_add_button:
            self.name_lbl.setStyleSheet(
                f"color: {t['text']}; font-size: 15px; font-weight: 500;"
            )
            self._apply_toggle_style()
        self._apply_selection_style()

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return super().mousePressEvent(event)
        pos = event.pos()
        child = self.childAt(pos)
        if isinstance(child, QPushButton):
            return super().mousePressEvent(event)
        if self.is_add_button and self.parent_app:
            self.parent_app.prompt_add_chat()
        elif self.parent_app and not self.is_add_button:
            self.parent_app.select_chat(self.user_id, self.full_name)
        super().mousePressEvent(event)
