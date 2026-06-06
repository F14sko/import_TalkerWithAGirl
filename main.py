import asyncio
import os
import sys
import threading
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
os.chdir(PROJECT_ROOT)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def configure_qt_plugins():
    try:
        import PyQt6

        qt_plugins = Path(PyQt6.__file__).resolve().parent / "Qt6" / "plugins"
        platforms = qt_plugins / "platforms"
        if platforms.is_dir():
            os.environ["QT_PLUGIN_PATH"] = str(qt_plugins)
            os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = str(platforms)
    except Exception as exc:
        print("Qt plugin path warning:", exc)


configure_qt_plugins()

from PyQt6.QtWidgets import QApplication, QDialog

from core import config
from core.config import SESSION_FILE, load_config 
from core import telegram_bot
from ui.main_window import MainApp
from ui.widgets import TelegramLoginDialog

app = None


def login_main():
    login_dialog = TelegramLoginDialog()
    if login_dialog.exec() != QDialog.DialogCode.Accepted:
        return


def run_login():
    login_main()


def run_asyncio_loop(loop_param):
    asyncio.set_event_loop(loop_param)
    loop_param.run_forever()


def run_main():
    global app
    config.reload_config() 
    telegram_bot.loop = asyncio.new_event_loop()
    window = MainApp()
    window.show()
    threading.Thread(
        target=run_asyncio_loop,
        args=(telegram_bot.loop,),
        daemon=True,
    ).start()
    sys.exit(app.exec())


def fiasko_main():
    global app
    app = QApplication(sys.argv)

    if not SESSION_FILE.exists():
        run_login()
        if not SESSION_FILE.exists():
            return

    run_main()


if __name__ == "__main__":
    fiasko_main()