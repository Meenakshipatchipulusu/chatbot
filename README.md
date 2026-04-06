# Chatbot Starter (Flask)

A minimal chatbot web app with:
- Flask backend
- Simple HTML/CSS/JS chat UI
- Hugging Face Inference API mode when `HUGGINGFACE_API_KEY` is set
- Voice input (speech-to-text in browser)
- File attachments from browser (`+` button), including PDF/text context

## 1) Create and activate virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

## 2) Install dependencies

```powershell
python -m pip install -r requirements.txt
```

## 3) Configure environment

```powershell
Copy-Item .env.example .env
```

Then edit `.env` and set:
- `HUGGINGFACE_API_KEY`
- optional: `HF_MODEL` (default: `meta-llama/Llama-3.1-8B-Instruct`)

## 4) Run app

```powershell
python app.py
```

Open `http://127.0.0.1:5000`.

## Notes
- If you see auth errors, verify the token is a valid Hugging Face access token and restart the server after updating `.env`.
