
# import TalkerWithAGirl

## 📌 Description

`TalkerWithAGirl` — a Python module for automating communication in Telegram using AI (Groq API + LLaMA).

The program analyzes incoming messages, builds conversation context, and generates responses in a natural, human-like chatting style.

---

# 📖 Instructions for using TalkerWithAGirl

---

## 1. Registration and obtaining keys

Before the first launch, you need to register:

📱 Telegram API

1. Go to:
   [https://my.telegram.org](https://my.telegram.org)
2. Log in to your account
3. Open API development tools
4. Obtain:

* API_ID
* API_HASH

---

## 2. First launch and authorization

1. Run the FiaskoAI.exe
2. Enter `API_ID` and `API_HASH`
3. Complete Telegram authorization
4. After login, a session file will be created:

```text id="sess01"
session.session
```

---

## 3. Configuration setup

All settings are configured directly in the app:

Open ⚙️ **Settings** and fill in:

* API ID
* API HASH
* API Key
* Self description (MY_BIO)
* PROMPT_INTRO (first mode)
* PROMPT_CHAT (second mode)

👉 After saving, everything is applied automatically

---

## 4. Bot startup

Press the button:

```text id="run01"
Connect
```

After launch, the bot:

* connects to Telegram
* starts listening to messages
* replies automatically using AI

---

## 5. Adding chats

Click **Add Chat** and confirm adding it

---

## 6. Chat management

For each chat, the following options are available:

* ON / OFF — enable bot
* Prompt 1 / 2 — toggle between prompts configured in settings
* Formal / Casual - toggle between formal and informal communication style. In formal, all punctuation is preserved; in informal, it is removed
* Sync chat - downloads the chat history from Telegram and adds it to the database

## 👤 Profile and Avatars

* **Avatars directory**: All downloaded and default avatars are stored in the `avatar/` folder.
* **Custom avatar**: You can change your profile avatar by clicking on it in the **Profile** tab and choosing an image from your computer.

---


## ⚠️ Important

* without API Key the bot will not respond
* without Telegram session, operation is impossible
* internet connection is required
* deleting session = re-login required

---

## 🚀 Done

---

# ⚙️ How it works

### Telegram authorization

Uses:

* `API_ID`
* `API_HASH`
* `TelegramClient (Telethon)`

After the first launch, a file is created:

```
session.session
```

It stores the Telegram session authentication.



### Database

SQLite is used to store:

**profiles**

* user_id
* username
* name
* status (active / paused)
* bot_mode
* language
* hobbies

**messages**

* chat_id
* sender_id
* text
* timestamp

---

### AI response generation

Supports multiple AI Models (Gemini, ChatGPT, Llama, Groq) via API keys:

* **Gemini**: `gemini-1.5-flash`
* **ChatGPT**: `gpt-4o-mini`
* **Llama**: `llama-3.1-8b-instant`
* **Groq**: `mixtral-8x7b-32768`

The request includes:

* user biography
* chat history
* interlocutor’s hobbies
* communication language
* selected mode

---

### Response logic

1. Receive message
2. Save to database
3. Update context
4. Analyze interests (if keywords exist)
5. Build prompt
6. Send request to AI
7. Split response into parts
8. Send to Telegram

---

### Hobby extraction

If a message contains triggers:

```
I like / I love / I do / I’m into
```

AI returns:

```json
["sports", "music", "coding"]
```

Data is stored in the user profile.

---

## 🧠 Working modes (user-defined)

There are **no fixed modes** in this system.

The user defines them via configuration:

```json
"PROMPT_INTRO": "..."
"PROMPT_CHAT": "..."
```

You can write it yourself and use it in any dialogue by simply enabling the desired prompt.

👉 Essentially, modes = custom prompts, not hardcoded logic.

---

## 📡 Errors

### API

* `ERR_API_401` — invalid API key
* `ERR_API_403` — access denied
* `ERR_API_429` — request limit exceeded
* `ERR_API_500` — server error
* `ERR_API_CONNECTION` — no connection

---

### Telegram

* `ERR_TELEGRAM_TIMEOUT` — connection timeout
* `ERR_CONNECT_FAIL` — client error

---

### AI / processing

* `ERR_JSON_PARSE` — response parsing error
* `ERR_RESPONSE_FAIL` — AI failed to generate response

---

## 🔧 Dependencies

Install dependencies

```bash
pip install -r requirements.txt
```

---

## 📂 Configuration

```text
config.json
```

Contains:

* Telegram API keys
* API key
* user biography
* models
* theme
* language
* timezone
* PROMPT_INTRO (mode 1)
* PROMPT_CHAT (mode 2)

---

## 🧩 Summary

`TalkerWithAGirl` is a Telegram AI bot that:

* analyzes conversations
* builds dialogue context
* generates responses using LLM
* is fully controlled via user-defined prompts (modes)
