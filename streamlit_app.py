import os
from io import BytesIO

import requests
import streamlit as st
from dotenv import load_dotenv
from pypdf import PdfReader


load_dotenv()

SYSTEM_PROMPT = "You are a helpful, concise chatbot assistant."
DEFAULT_HF_MODEL = "meta-llama/Llama-3.1-8B-Instruct"
FALLBACK_MODELS = [
    DEFAULT_HF_MODEL,
    "mistralai/Mistral-7B-Instruct-v0.3",
    "Qwen/Qwen2.5-7B-Instruct",
]
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


def get_secret(name, default=""):
    try:
        value = st.secrets.get(name, default)
    except Exception:
        value = default
    return str(value).strip()


def get_hf_api_key():
    return (
        get_secret("HUGGINGFACE_API_KEY")
        or get_secret("HF_API_KEY")
        or os.getenv("HUGGINGFACE_API_KEY", "").strip()
        or os.getenv("HF_API_KEY", "").strip()
    )


def get_hf_model():
    return (
        get_secret("HF_MODEL")
        or os.getenv("HF_MODEL", "").strip()
        or DEFAULT_HF_MODEL
    )


def read_uploaded_excerpt(uploaded_file):
    name = uploaded_file.name or "file"
    ext = os.path.splitext(name)[1].lower()

    if ext not in ALLOWED_EXTENSIONS:
        return {
            "name": name,
            "error": f"Unsupported file type: {ext or 'unknown'}",
        }

    try:
        data = uploaded_file.getvalue()
        if ext == ".pdf":
            reader = PdfReader(BytesIO(data))
            text = "\n".join((page.extract_text() or "") for page in reader.pages[:10])
        else:
            text = data.decode("utf-8", errors="ignore")

        return {
            "name": name,
            "size": len(data),
            "text_excerpt": text[:4500],
        }
    except Exception as exc:
        return {
            "name": name,
            "error": f"Could not read file: {exc}",
        }


def build_attachment_context(attachments):
    lines = []
    budget = 7000

    for item in attachments:
        excerpt = (item.get("text_excerpt") or "").strip()
        if not excerpt:
            continue

        block = f"File: {item.get('name', 'file')}\n{excerpt}\n"
        if len(block) > budget:
            block = block[:budget]
        lines.append(block)
        budget -= len(block)

        if budget <= 0:
            break

    if not lines:
        return ""

    return "Use the following attached file context when answering.\n\n" + "\n".join(lines)


def build_messages(user_message, history, attachments):
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    for item in history:
        role = item.get("role")
        content = (item.get("content") or "").strip()
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})

    attachment_context = build_attachment_context(attachments)
    if attachment_context:
        messages.append({"role": "system", "content": attachment_context})

    messages.append({"role": "user", "content": user_message})
    return messages


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


def call_hf_inference(model_name, messages, hf_api_key):
    response = requests.post(
        "https://router.huggingface.co/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {hf_api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model_name,
            "messages": messages,
            "max_tokens": 300,
            "temperature": 0.7,
        },
        timeout=60,
    )
    return response


def get_chatbot_reply(user_message, history, attachments):
    hf_api_key = get_hf_api_key()
    if not hf_api_key:
        raise RuntimeError(
            "Missing Hugging Face key. Add HUGGINGFACE_API_KEY in Streamlit secrets."
        )

    messages = build_messages(user_message, history, attachments)
    selected_model = get_hf_model()
    models_to_try = [selected_model] + [
        model for model in FALLBACK_MODELS if model != selected_model
    ]

    response = None
    for model_name in models_to_try:
        response = call_hf_inference(model_name, messages, hf_api_key)

        if response.status_code == 401:
            raise RuntimeError("Invalid Hugging Face API key.")

        if is_model_unavailable_error(response):
            continue

        break

    if response is None or response.status_code >= 400:
        status_code = response.status_code if response is not None else 500
        error_text = response.text if response is not None else "No response from model."
        raise RuntimeError(f"Hugging Face error ({status_code}): {error_text}")

    data = response.json()
    choices = data.get("choices") or []
    if choices and isinstance(choices[0], dict):
        message = choices[0].get("message") or {}
        reply = (message.get("content") or "").strip()
        if reply:
            return reply

    return "I could not generate a response this time. Please try again."


st.set_page_config(page_title="Chatbot", page_icon=":material/chat:", layout="centered")

st.markdown(
    """
    <style>
    :root {
        --ink: #17201a;
        --leaf: #2f6f4e;
        --cream: #f8f1df;
        --sand: #ead7ad;
    }

    .stApp {
        background:
            radial-gradient(circle at top left, rgba(47, 111, 78, 0.2), transparent 32rem),
            linear-gradient(135deg, var(--cream), #fffaf0 58%, var(--sand));
        color: var(--ink);
    }

    .hero-card {
        border: 1px solid rgba(23, 32, 26, 0.12);
        border-radius: 28px;
        padding: 1.25rem 1.4rem;
        background: rgba(255, 252, 244, 0.78);
        box-shadow: 0 24px 70px rgba(63, 45, 20, 0.14);
        margin-bottom: 1rem;
    }

    .hero-card h1 {
        color: var(--ink);
        font-family: Georgia, 'Times New Roman', serif;
        font-size: clamp(2.2rem, 7vw, 4rem);
        line-height: 0.95;
        margin: 0 0 0.65rem;
        letter-spacing: -0.05em;
    }

    .hero-card p {
        color: rgba(23, 32, 26, 0.78);
        font-size: 1.05rem;
        margin: 0;
    }

    [data-testid="stChatMessage"] {
        border-radius: 22px;
        border: 1px solid rgba(23, 32, 26, 0.08);
        background: rgba(255, 252, 244, 0.66);
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="hero-card">
        <h1>Chatbot</h1>
        <p>Ask a question, attach context files, and get a Hugging Face powered answer.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

if "messages" not in st.session_state:
    st.session_state.messages = []
if "attachments" not in st.session_state:
    st.session_state.attachments = []

with st.sidebar:
    st.header("Settings")
    st.caption(f"Model: `{get_hf_model()}`")

    uploaded_files = st.file_uploader(
        "Attach files for context",
        type=[ext.lstrip(".") for ext in sorted(ALLOWED_EXTENSIONS)],
        accept_multiple_files=True,
    )

    if uploaded_files:
        st.session_state.attachments = [
            read_uploaded_excerpt(uploaded_file) for uploaded_file in uploaded_files
        ]

    for attachment in st.session_state.attachments:
        if "error" in attachment:
            st.warning(f"{attachment['name']}: {attachment['error']}")
        else:
            st.success(f"{attachment['name']} added")

    if st.button("Clear chat", use_container_width=True):
        st.session_state.messages = []
        st.session_state.attachments = []
        st.rerun()

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

prompt = st.chat_input("Message the chatbot")

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                history = st.session_state.messages[:-1]
                reply = get_chatbot_reply(
                    prompt,
                    history,
                    st.session_state.attachments,
                )
                st.markdown(reply)
            except Exception as exc:
                reply = f"Sorry, I hit an error: {exc}"
                st.error(reply)

    st.session_state.messages.append({"role": "assistant", "content": reply})
