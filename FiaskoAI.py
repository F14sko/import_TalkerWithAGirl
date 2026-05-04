import os
import subprocess

SESSION_FILE = "session.session"


def run_login():
    subprocess.run(["login.exe"])


def run_main():
    subprocess.run(["main.exe"])


def main():
    if not os.path.exists(SESSION_FILE):
        run_login()

        if not os.path.exists(SESSION_FILE):
            return

    run_main()


if __name__ == "__main__":
    main()
