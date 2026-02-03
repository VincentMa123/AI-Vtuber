# AI VTuber Project

This project consists of a Python-based backend (FastAPI) and a Next.js frontend (React), creating an interactive AI VTuber with LLM (Large Language Model), TTS (Text-to-Speech), and Vision capabilities.

https://github.com/user-attachments/assets/7fa66717-6485-4ab1-84f9-e7ba645a2ed7


## ⚠️ Important Notes

- **Inference Speed**: The response time for LLM and TTS may vary significantly depending on your internet connection speed, especially when using remote providers.
- **Voice Cloning**: The current TTS implementation uses voice cloning technology. You may notice some imperfections in the voice generation.
    - *Tip*: If audio quality is critical, you can switch to a TTS engine that doesn't use voice cloning (configurable in `TTS_PROVIDER`), though this may limit your options for custom character voices.


## Prerequisites

- **Python 3.10+** (Recommend 3.11 or 3.12)
- **Node.js 18+**

## 🚀 Backend Setup (src)

1.  **Navigate to the project root.**

2.  **Create and activate a virtual environment (recommended):**
    ```bash
    python -m venv venv
    # Windows
    venv\Scripts\activate
    # Linux/Mac
    source venv/bin/activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r src/requirements.txt
    ```

4.  **Configuration:**
    - Ensure you have a `.env` file in the `src/` directory if required by the application (check `core/config.py` or existing `.env` for keys like API tokens for OpenRouter/DeepSeek/Twitch).

5.  **Run the Backend:**
    You can run the server directly using Python:
    ```bash
    # Run from the project root
    python src/api_server.py
    ```
    The server will start on `http://localhost:8000`.

## ⚙️ Configuration

The application uses environment variables for configuration. Create a `.env` file in the `src/` directory (or ensure your environment has these variables set).

### Required API Keys

| Variable | Description |
| :--- | :--- |
| `OPENROUTER_API_KEY` | API key for OpenRouter (if using OpenRouter provider). |
| `DEEPSEEK_API_KEY` | API key for DeepSeek (if using DeepSeek provider). |
| `QWEN_API_KEY` | API key for Qwen/DashScope (if using Qwen provider). |
| `ELEVENLABS_API_KEY` | API key for ElevenLabs (if using ElevenLabs TTS). |

### Twitch Integration (Optional)

| Variable | Description |
| :--- | :--- |
| `TWITCH_BOT_TOKEN` | OAuth token for the Twitch bot (get from [twitchtokengenerator.com](https://twitchtokengenerator.com/)). |
| `TWITCH_CHANNEL` | The Twitch channel name for the bot to join. |

### Other Configuration (Optional/Defaults)

| Variable | Default | Description |
| :--- | :--- | :--- |
| `TTS_PROVIDER` | `realtimetts` | Choose between `realtimetts` or `qwen`. |
| `REALTIMETTS_ENGINE` | `system` | Turbo-charged local TTS (`system`) or `elevenlabs`. |
| `REMOTE_VLLM_BASE_URL` | *(Pre-configured)* | URL for remote vLLM instance. |

**Example `.env` file:**

```ini
OPENROUTER_API_KEY=sk-or-v1-...
DEEPSEEK_API_KEY=sk-...
QWEN_API_KEY=sk-...
ELEVENLABS_API_KEY=...
TWITCH_BOT_TOKEN=oauth:...
TWITCH_CHANNEL=mychannelname
```

---

## 🎨 Frontend Setup (vtuber)

1.  **Navigate to the frontend directory:**
    ```bash
    cd vtuber
    ```

2.  **Install dependencies:**
    ```bash
    npm install
    # or yarn install / pnpm install
    ```

3.  **Run the Development Server:**
    ```bash
    npm run dev
    ```

4.  **Access the Application:**
    Open [http://localhost:3000](http://localhost:3000) in your browser.

## Features

- **LLM Integration**: Supports OpenRouter, DeepSeek, Qwen and Remote VLLM.
- **RAG (Retrieval-Augmented Generation)**: Product search logic in `src/rag`.
- **TTS**: RealtimeTTS integration for low-latency voice.
- **Vision**: Analyzes browser screenshots/audio to react to content.
- **Live2D Frontend**: Displays the VTuber model using PixiJS.
- **Twitch Integration**: Optional bot for Twitch chat interaction.



