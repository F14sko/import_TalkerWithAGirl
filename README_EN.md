
# import TalkerWithAGirl

## 📌 Description

`TalkerWithAGirl` — a Python module for automating communication in Telegram using AI (Groq API + LLaMA).

The program analyzes incoming messages, builds conversation context, and generates responses in a natural, human-like chatting style.

---

# 📖 Instructions for using TalkerWithAGirl

## 1. Install dependencies

```bash
pip install telethon aiohttp aiosqlite PyQt6
```

---

## 2. Registration and obtaining keys

Before the first launch, you need to register:

📱 Telegram API

1. Go to:
   [https://my.telegram.org](https://my.telegram.org)
2. Log in to your account
3. Open API development tools
4. Obtain:

* API_ID
* API_HASH

🤖 Groq API (AI key)

1. Go to:
   [https://console.groq.com](https://console.groq.com)
2. Sign up / log in
3. Create an API Key
4. Copy the key for use in the application

---

## 3. First launch and authorization

1. Run the FiaskoAI.exe
2. Enter `API_ID` and `API_HASH`
3. Complete Telegram authorization
4. After login, a session file will be created:

```text id="sess01"
session.session
```

---

## 4. Configuration setup

All settings are configured directly in the app:

Open ⚙️ **Settings** and fill in:

* API ID
* API HASH
* Groq API Key
* Self description (MY_BIO)
* PROMPT_INTRO (dialog start mode)
* PROMPT_CHAT (chat mode)

👉 After saving, everything is applied automatically

---

## 5. Bot startup

Press the button:

```text id="run01"
Connect
```

After launch, the bot:

* connects to Telegram
* starts listening to messages
* replies automatically using AI

---

## 6. Adding chats

Click **Add Chat** and confirm adding it

---

## 7. Chat management

For each chat, the following options are available:

* ON / OFF — enable bot
* 1 / 2 — chat mode
* LAN — language (RU / EN)
* ⋮ — additional actions

---

## ⚠️ Important

* without Groq API Key the bot will not respond
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

---

### Message processing

When a new message is received:

* checks that the chat is private
* saves the message to SQLite
* cleans unnecessary symbols
* detects language (RU / EN)
* updates conversation context

---

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

Uses Groq API:

```python
model = "llama-3.1-8b-instant"
```

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

### 🔹 PROMPT_INTRO

Used for starting a dialogue:

* defines the style of first contact
* determines AI behavior at the beginning of communication

### 🔹 PROMPT_CHAT

Used in active conversations:

* communication style
* tone, brevity, response manner

👉 Essentially, modes = custom prompts, not hardcoded logic.

---

## 📡 Errors

### Groq API

* `ERR_GROQ_401` — invalid API key
* `ERR_GROQ_403` — access denied
* `ERR_GROQ_429` — request limit exceeded
* `ERR_GROQ_500` — server error
* `ERR_GROQ_CONNECTION` — no connection

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

* `telethon` — Telegram API
* `aiohttp` — HTTP requests
* `aiosqlite` — database
* `PyQt6` — UI
* `asyncio` — asynchronous execution

---

## 📂 Configuration

```text
config.json
```

Contains:

* Telegram API keys
* Groq API key
* user biography
* PROMPT_INTRO (mode 1)
* PROMPT_CHAT (mode 2)

---

## 🧩 Summary

`TalkerWithAGirl` is a Telegram AI bot that:

* analyzes conversations
* builds dialogue context
* generates responses using LLM
* is fully controlled via user-defined prompts (modes)
