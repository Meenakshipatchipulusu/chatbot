# Chatbot Starter

A minimal chatbot web app with two entrypoints:
- `streamlit_app.py` for Streamlit Community Cloud
- `app.py` for the original Flask version
- Hugging Face Inference API mode when `HUGGINGFACE_API_KEY` is set
- File attachments, including PDF/text context

## 1) Create and activate virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

## 2) Install dependencies

```powershell
python -m pip install -r requirements.txt
```

## 3) Configure environment locally

```powershell
New-Item .env -ItemType File
```

Then edit `.env` and set:
- `HUGGINGFACE_API_KEY`
- optional: `HF_MODEL` (default: `meta-llama/Llama-3.1-8B-Instruct`)

## 4) Run Streamlit app locally

```powershell
streamlit run streamlit_app.py
```

## 5) Deploy to Streamlit Community Cloud

1. Push this project to GitHub.
2. Go to `https://share.streamlit.io`.
3. Click **Create app**.
4. Select your repository, branch, and main file path:

```text
streamlit_app.py
```

5. Open **Advanced settings** and add this secret:

```toml
HUGGINGFACE_API_KEY = "your_hugging_face_token_here"
# Optional:
HF_MODEL = "meta-llama/Llama-3.1-8B-Instruct"
```

6. Click **Deploy**.

## Flask app locally

```powershell
python app.py
```

Open `http://127.0.0.1:10000`.

## Notes
- If you see auth errors, verify the token is a valid Hugging Face access token and restart the server after updating `.env`.
- Do not commit `.env` or `.streamlit/secrets.toml`; use Streamlit secrets for deployment.
