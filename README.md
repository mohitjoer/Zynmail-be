# ⚡ Zynmail Backend (`Zynmail-be`)

The asynchronous, AI-accelerated backend service for **Zynmail**, powered by FastAPI, Python 3.13+, LangChain, and Motor/MongoDB.

---

## 🛠️ Tech Stack

- **Framework**: [FastAPI](https://fastapi.tiangolo.com/) with [Uvicorn](https://www.uvicorn.org/) ASGI
- **Runtime & Packaging**: [Python 3.13+](https://www.python.org/) managed via [uv](https://astral.sh/uv)
- **Database**: [MongoDB](https://www.mongodb.com/) via [Motor](https://motor.readthedocs.io/) (AsyncIO Driver)
- **AI & LLMs**: [LangChain](https://www.langchain.com/), [LangGraph](https://langchain-ai.github.io/langgraph/), [Groq](https://groq.com/)
- **Security & Encryption**: AES-256 Fernet authenticated field-level encryption
- **Integrations**: Google APIs Client Library, Google OAuthlib, Bleach (HTML Sanitization)

---

## 📁 Directory Structure

```text
Zynmail-be/
├── app/
│   ├── main.py                   # FastAPI app entry point & CORS configuration
│   ├── database.py               # Motor MongoDB async client & lifecycle hooks
│   ├── config.py                 # Pydantic Settings & environment loader
│   │
│   ├── routes/                   # API Routers
│   │   ├── emails.py             # Email listing, threading, search, & background sync
│   │   ├── auth.py               # Google OAuth authorization URL & token exchange
│   │   ├── users.py              # User profile endpoints & settings updates
│   │   ├── automations.py        # LangGraph / n8n workflow triggers & nodes
│   │   └── security.py           # Encryption health status & telemetry
│   │
│   ├── services/                 # Core Business Logic
│   │   ├── gmail_service.py      # Google Gmail REST API syncing & RFC822 parser
│   │   ├── ai_classifier.py      # AI categorization (Work, Personal, Promotions, etc.)
│   │   ├── encryption_service.py # AES-256 Fernet encryption for data at rest
│   │   └── prompt_guard.py       # Prompt injection defenses & output sanitization
│   │
│   └── models/                   # Pydantic Models & Schemas
│       ├── email.py              # Email, Thread, Contact, and Folder schemas
│       └── user.py               # User and Auth response schemas
│
├── tests/                        # Pytest async test suite
│   └── test_api.py               # Health check, email, and profile tests
│
├── .env.example                  # Environment configuration template
├── pyproject.toml                # Dependencies and project metadata
└── pytest.ini                    # Pytest configuration
```

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.13+**
- **`uv` package manager** (recommended):
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```

---

### 1. Environment Setup

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Configure your `.env` variables:

```env
MONGODB_URL="mongodb+srv://<username>:<password>@cluster.mongodb.net/?retryWrites=true&w=majority"
DATABASE_NAME="zynmail"
APP_NAME="Zynmail"
DEBUG=true
CORS_ORIGINS="http://localhost:3000"

# Groq API Key (https://console.groq.com/)
GROQ_API_KEY="gsk_your_groq_key"

# AES-256 Fernet Encryption Key
# Generate one with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
ENCRYPTION_KEY="your_base64_fernet_key"
```

### 2. Google OAuth Credentials

Download your `client_secret.json` from the [Google Cloud Console](https://console.cloud.google.com/apis/credentials) and place it inside the `Zynmail-be/` directory:

```text
Zynmail-be/client_secret.json
```

Ensure your redirect URI in Google Cloud Console includes:
`http://localhost:3000/home`

---

### 3. Run the Development Server

Using `uv`:

```bash
uv run uvicorn app.main:app --reload --port 8000
```

Alternatively, with a virtual environment:

```bash
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

- API Base URL: **`http://127.0.0.1:8000`**
- Interactive Swagger Docs: **`http://127.0.0.1:8000/docs`**
- ReDoc Docs: **`http://127.0.0.1:8000/redoc`**

---

## 🧪 Running Tests

Run the full pytest suite with async support:

```bash
uv run pytest
```

---

## 🔒 Security Architecture

- **Token Protection**: OAuth tokens and credentials stored in `user_credentials.json` are encrypted using **AES-256-CBC-HMAC** (Fernet) with keys derived from `ENCRYPTION_KEY`.
- **Sanitization**: Raw incoming HTML email bodies are sanitized with `bleach` and `prompt_guard` to prevent XSS and prompt injection attacks.
- **Background Sync**: Heavy Gmail synchronization operations execute asynchronously using FastAPI `BackgroundTasks` without blocking API response times.
