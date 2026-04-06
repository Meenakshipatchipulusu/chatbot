import os
import json
import uuid
from pathlib import Path
import requests
from werkzeug.utils import secure_filename
from flask import Flask, Response, jsonify, render_template, request, stream_with_context
from dotenv import load_dotenv
from pypdf import PdfReader

load_dotenv()

app = Flask(__name__)
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

ALLOWED_EXTENSIONS = {
    ".pdf",
    ".txt",
    ".md",
    ".csv",
    ".json",
    ".log",
    ".py",
    ".html",
    ".js",
}
MAX_FILE_SIZE_BYTES = 8 * 1024 * 1024

SYSTEM_PROMPT = "You are a helpful, concise chatbot assistant."
DEFAULT_HF_MODEL = "meta-llama/Llama-3.1-8B-Instruct"
HF_MODEL = os.getenv("HF_MODEL", DEFAULT_HF_MODEL).strip() or DEFAULT_HF_MODEL
FALLBACK_MODELS = [
    DEFAULT_HF_MODEL,
    "mistralai/Mistral-7B-Instruct-v0.3",
    "Qwen/Qwen2.5-7B-Instruct",
]


def get_hf_api_key():
    # Accept both names to avoid setup mistakes.
    return (
        os.getenv("HUGGINGFACE_API_KEY", "").strip()
        or os.getenv("HF_API_KEY", "").strip()
    )


def build_attachment_context(attachments):
    if not isinstance(attachments, list):
        return ""

    lines = []
    budget = 7000
    for item in attachments:
        if not isinstance(item, dict):
            continue
        name = (item.get("name") or "file").strip()
        excerpt = (item.get("text_excerpt") or "").strip()
        if not excerpt:
            continue
        block = f"File: {name}\n{excerpt}\n"
        if len(block) > budget:
            block = block[:budget]
        lines.append(block)
        budget -= len(block)
        if budget <= 0:
            break

    if not lines:
        return ""

    return "Use the following attached file context when answering.\n\n" + "\n".join(lines)


def build_messages(user_message, history, attachments=None):
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    if isinstance(history, list):
        for item in history:
            if not isinstance(item, dict):
                continue
            role = (item.get("role") or "").strip()
            content = (item.get("content") or "").strip()
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})

    attachment_context = build_attachment_context(attachments or [])
    if attachment_context:
        messages.append({"role": "system", "content": attachment_context})

    messages.append({"role": "user", "content": user_message})
    return messages


def read_text_excerpt(path, ext):
    try:
        if ext == ".pdf":
            reader = PdfReader(str(path))
            parts = []
            for page in reader.pages[:10]:
                parts.append(page.extract_text() or "")
            text = "\n".join(parts)
            return text[:4500]

        text = path.read_text(encoding="utf-8", errors="ignore")
        return text[:4500]
    except Exception:
        return ""


def is_model_unavailable_error(response):
    if response.status_code not in (400, 404):
        return False
    text = (response.text or "").lower()
    markers = [
        "model_not_supported",
        "not supported",
        "not found",
        "does not exist",
        "no provider",
    ]
    return any(marker in text for marker in markers)


def call_hf_inference(model_name, messages, hf_api_key, stream=False):
    api_url = "https://router.huggingface.co/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {hf_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model_name,
        "messages": messages,
        "max_tokens": 220,
        "temperature": 0.7,
        "stream": stream,
    }
    return requests.post(api_url, headers=headers, json=payload, timeout=60, stream=stream)


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/upload", methods=["POST"])
def upload_files():
    files = request.files.getlist("files")
    if not files:
        return jsonify({"error": "No files uploaded"}), 400

    uploaded = []
    for file in files:
        original_name = (file.filename or "").strip()
        if not original_name:
            continue

        safe_name = secure_filename(original_name)
        ext = Path(safe_name).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            uploaded.append(
                {
                    "name": original_name,
                    "error": f"Unsupported file type: {ext or 'unknown'}",
                }
            )
            continue

        file.stream.seek(0, os.SEEK_END)
        size = file.stream.tell()
        file.stream.seek(0)
        if size > MAX_FILE_SIZE_BYTES:
            uploaded.append(
                {
                    "name": original_name,
                    "error": f"File too large ({size} bytes). Max is {MAX_FILE_SIZE_BYTES} bytes.",
                }
            )
            continue

        unique_name = f"{uuid.uuid4().hex}_{safe_name}"
        path = UPLOAD_DIR / unique_name
        file.save(path)
        excerpt = read_text_excerpt(path, ext)

        uploaded.append(
            {
                "name": original_name,
                "size": size,
                "type": file.mimetype or "application/octet-stream",
                "text_excerpt": excerpt,
            }
        )

    return jsonify({"files": uploaded})


@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True) or {}
    user_message = (data.get("message") or "").strip()
    history = data.get("history") or []
    attachments = data.get("attachments") or []

    if not user_message:
        return jsonify({"error": "message is required"}), 400

    hf_api_key = get_hf_api_key()
    if not hf_api_key:
        return jsonify(
            {"error": "Missing Hugging Face key. Set HUGGINGFACE_API_KEY in .env."}
        ), 500

    try:
        messages = build_messages(user_message, history, attachments)
        models_to_try = [HF_MODEL] + [m for m in FALLBACK_MODELS if m != HF_MODEL]
        response = None

        for model_name in models_to_try:
            response = call_hf_inference(model_name, messages, hf_api_key)

            if response.status_code == 401:
                return jsonify({"error": "Invalid Hugging Face API key"}), 401

            # Retry with another model when chosen model is unavailable for this account/provider.
            if is_model_unavailable_error(response):
                continue

            # Any non-retryable status or success exits loop.
            break

        if response is None or response.status_code >= 400:
            return jsonify(
                {
                    "error": f"Hugging Face error ({response.status_code}): {response.text}"
                }
            ), 500

        data = response.json()

        reply = ""
        if isinstance(data, dict):
            if "error" in data:
                return jsonify({"error": f"Hugging Face error: {data['error']}"}), 500
            choices = data.get("choices") or []
            if choices and isinstance(choices[0], dict):
                message = choices[0].get("message") or {}
                reply = (message.get("content") or "").strip()

        if not reply:
            reply = "I could not generate a response this time. Please try again."

        return jsonify({"reply": reply})

    except requests.RequestException as exc:
        return jsonify({"error": f"Request failed: {exc}"}), 500


@app.route("/chat/stream", methods=["POST"])
def chat_stream():
    data = request.get_json(silent=True) or {}
    user_message = (data.get("message") or "").strip()
    history = data.get("history") or []
    attachments = data.get("attachments") or []

    if not user_message:
        return jsonify({"error": "message is required"}), 400

    hf_api_key = get_hf_api_key()
    if not hf_api_key:
        return jsonify(
            {"error": "Missing Hugging Face key. Set HUGGINGFACE_API_KEY in .env."}
        ), 500

    messages = build_messages(user_message, history, attachments)
    models_to_try = [HF_MODEL] + [m for m in FALLBACK_MODELS if m != HF_MODEL]
    response = None

    try:
        for model_name in models_to_try:
            response = call_hf_inference(model_name, messages, hf_api_key, stream=True)

            if response.status_code == 401:
                return jsonify({"error": "Invalid Hugging Face API key"}), 401

            if is_model_unavailable_error(response):
                continue

            break

        if response is None or response.status_code >= 400:
            status_code = response.status_code if response is not None else 500
            error_text = response.text if response is not None else "No response from model."
            return jsonify({"error": f"Hugging Face error ({status_code}): {error_text}"}), 500

        @stream_with_context
        def generate():
            try:
                for raw_line in response.iter_lines(decode_unicode=True):
                    if not raw_line:
                        continue
                    if not raw_line.startswith("data: "):
                        continue

                    payload = raw_line[6:].strip()
                    if payload == "[DONE]":
                        break

                    try:
                        event = json.loads(payload)
                    except json.JSONDecodeError:
                        continue

                    choices = event.get("choices") or []
                    if not choices:
                        continue
                    delta = choices[0].get("delta") or {}
                    token = delta.get("content") or ""
                    if token:
                        yield token
            finally:
                response.close()

        return Response(generate(), mimetype="text/plain")

    except requests.RequestException as exc:
        return jsonify({"error": f"Request failed: {exc}"}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
