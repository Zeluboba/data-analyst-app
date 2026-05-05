import streamlit as st
import boto3
import asyncio
import websockets

WS_URL = "wss://d5dfd6buaipmjov5en9g.y3q8o1jq.apigw.yandexcloud.net"


AWS_ACCESS_KEY_ID = st.secrets["AWS_ACCESS_KEY_ID"]
AWS_SECRET_ACCESS_KEY = st.secrets["AWS_SECRET_ACCESS_KEY"]
BUCKET = "data-analyst-files"

s3 = boto3.client(
    "s3",
    endpoint_url="https://storage.yandexcloud.net",
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
)


def upload_to_s3(file, filename):
    """Загружает файл в Yandex Object Storage."""
    try:
        file.seek(0)
        s3.upload_fileobj(file, BUCKET, filename)
        return True
    except Exception as e:
        st.error(f"Ошибка загрузки файла {filename}: {e}")
        return False


async def ask_agent(message: str) -> str:
    """Отправляет вопрос агенту через WebSocket и возвращает ответ."""
    result = []
    try:
        async with websockets.connect(WS_URL, ping_timeout=300) as ws:
            await ws.send(message)
            try:
                while True:
                    chunk = await asyncio.wait_for(ws.recv(), timeout=60.0)
                    if isinstance(chunk, bytes):
                        chunk = chunk.decode("utf-8")
                    if "[TOOL_CALL_START]" in chunk or "[TOOL_CALL_END]" in chunk:
                        continue
                    result.append(chunk)
            except asyncio.TimeoutError:
                pass
    except Exception as e:
        return f"Ошибка подключения к агенту: {e}"
    return "".join(result) or "Агент не вернул ответ."


# ── UI ────────────────────────────────────────────────────────────────────────

st.title("🤖 AI Аналитик данных")
st.caption("Загрузите CSV файлы и задайте вопрос агенту")

# Загрузка файлов
uploaded_files = st.file_uploader(
    "Загрузите CSV файлы",
    type=["csv"],
    accept_multiple_files=True,
)

uploaded_names = []
if uploaded_files:
    with st.spinner("Загрузка файлов в хранилище..."):
        for file in uploaded_files:
            if upload_to_s3(file, file.name):
                uploaded_names.append(file.name)

    if uploaded_names:
        st.success(f"✅ Загружено файлов: {len(uploaded_names)}")
        for name in uploaded_names:
            st.write(f"- `{name}`")

# История сообщений
if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

# Ввод вопроса
if question := st.chat_input("Задайте вопрос агенту..."):
    # Формируем вопрос с контекстом файлов
    if uploaded_names:
        files_info = ", ".join(uploaded_names)
        full_question = f"{question}\n\nДоступные файлы в хранилище: {files_info}"
    else:
        full_question = question

    # Показываем вопрос пользователя
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.write(question)

    # Получаем и показываем ответ агента
    with st.chat_message("assistant"):
        with st.spinner("Агент думает..."):
            answer = asyncio.run(ask_agent(full_question))
        st.write(answer)
        st.session_state.messages.append({"role": "assistant", "content": answer})
