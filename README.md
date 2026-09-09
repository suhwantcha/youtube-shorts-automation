# 🎬 Tech Shorts Studio - Unified Architecture

**GPT-4o Storytelling + Web UI + Automated Multi-Platform Upload**

This project is an **all-in-one short-form automation studio** that automatically creates engaging short-form videos based on the latest IT/tech trends and publishes them to YouTube Shorts, TikTok, and Instagram Reels.

**Key Architecture**: The pipeline is orchestrated as a single unified Python package (`tech_shorts`) with a **Web UI/API server**. You can easily run and manage it locally without the need for complex cloud infrastructure.

---

## 🌟 Core Features

### 🖥️ Integrated Web Studio & API
- **Dashboard UI**: Directly monitor task progress, manage approvals/rejections, and initiate manual generation through your browser (`http://127.0.0.1:8080`).
- **RESTful API**: Provides a powerful API that easily integrates with external automation tools. (See `docs/API.md`)
- **Local-First Design**: Uses SQLite by default to store jobs locally, eliminating the need for heavy cloud infrastructure setups.

### 🤖 Intelligent Content Creation
- **Trend Collection**: Automated content sourcing based on Hacker News and Reddit trends.
- **Storytelling Scripts**: Utilizes GPT-4o to generate storytelling scripts with strong hooks and sales text.
- **High-Quality TTS & Automated Video**: OpenAI/Google TTS for voice, high-definition 9:16 Pexels videos, Whisper timestamped subtitles, and automated FFmpeg synthesis.
- **Multi-Platform Upload**: One-click automatic uploading to YouTube, TikTok, and Instagram, complete with smart metadata (titles, hashtags).

---

## 📦 Project Structure

```
tech-shorts-production/
├── tech_shorts/             # Core application package
│   ├── web.py               # Web API and UI router (FastAPI based)
│   ├── pipeline.py          # Full video generation pipeline orchestration
│   ├── content.py           # Trend analysis and GPT script generation
│   ├── media.py             # Pexels video downloads and FFmpeg synthesis
│   ├── publishers.py        # SNS platform uploads (YouTube, TikTok, Instagram)
│   └── ...
├── docs/                    # Technical documentation, API guides, etc.
├── tests/                   # Unit/Integration tests
├── pyproject.toml           # Project dependencies and configurations
├── Start-Studio.ps1         # Script to run the local Web Studio
├── setup.ps1                # Automated local environment setup script
└── README.md                # This file
```

---

## 🚀 Quick Start Guide (Local Execution)

### 1. Environment Setup and Installation
Run the setup script in Windows PowerShell to automatically install dependencies.

```powershell
.\setup.ps1
```

### 2. API Key Configuration (Security)
Copy the `.env.example` file to create a `.env` file and enter your issued API keys.
**Note**: The `.env` file and `secrets/` folder are safely ignored from GitHub via `.gitignore`. Never commit your personal keys to GitHub!

```bash
cp .env.example .env
```
- Required Keys: `OPENAI_API_KEY`, `PEXELS_API_KEY`, `SHORTS_API_TOKEN` (an arbitrary string for API communication)

### 3. Start the Studio
Run the following script to open the local Web server.

```powershell
.\Start-Studio.ps1
```
Afterward, access `http://127.0.0.1:8080` in your browser to use the Studio UI!

---

## 🔐 Security and Authentication
- **API Authentication**: External scripts or calls require the `Authorization: Bearer <SHORTS_API_TOKEN>` header.
- **Browser Security**: The Web UI is protected via CSRF tokens and login sessions.
- **Secret Management**: All authentication tokens and sensitive data are injected from environment variables (`.env`). Do not hardcode any API keys at the code level.