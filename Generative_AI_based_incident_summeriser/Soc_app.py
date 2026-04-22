import chainlit as cl
from chainlit.input_widget import Select
import base64
import mimetypes
import time
import uuid

from openai import AsyncOpenAI
import chromadb
from chromadb.config import Settings
from PyPDF2 import PdfReader
from sentence_transformers import SentenceTransformer

from final_report_manager_1 import FinalReportManager


client = AsyncOpenAI(api_key="lm-studio", base_url="http://127.0.0.1:1234/v1")
embedding_model = SentenceTransformer("all-MiniLM-L6-v2")

MODEL_CONFIGS = {
    "qwen/qwen3-vl-4b": {
        "model": "qwen/qwen3-vl-4b",
        "temperature": 0.5,
        "max_tokens": 4000,
        "top_p": 1,
        "frequency_penalty": 0,
        "presence_penalty": 0,
        "is_vision": True,
    },
    "qwen/qwen3-4b": {
        "model": "qwen/qwen3-4b",
        "temperature": 0.5,
        "max_tokens": 4000,
        "top_p": 1,
        "frequency_penalty": 0,
        "presence_penalty": 0,
        "is_vision": False,
    },
    "qwen/qwen3-1.7b": {
        "model": "qwen/qwen3-1.7b",
        "temperature": 0.5,
        "max_tokens": 4000,
        "top_p": 1,
        "frequency_penalty": 0,
        "presence_penalty": 0,
        "is_vision": False,
    },
}

SYSTEM_PROMPT = "You are a helpful assistant. Answer questions based only on the provided context."
REPORT_QUESTION_PREFIX = "REPORT QUESTION:"

FINAL_REPORT_PROMPT = """
You are an expert SOC analyst writing a readable investigation report.

Output format (Markdown):
- Use Markdown headings for every section (use "#", "##").
- Write narrative paragraphs (no bullet points), EXCEPT the 5Ws can be bullet points.
- Do NOT wrap the report in code fences (no ```).

Accuracy rules:
- Use ONLY the provided summaries. Do NOT invent IPs/hosts/users/timestamps/actions.
- If something is missing, say "Unknown (not present in the file)."

Writing rules:
- Each section must be at least 4 sentences (detailed and readable).

Structure (use these as Markdown headings):
# Investigation Report

## 1. Validation / Detection

## 5Ws
(You may use bullet points here only.)

## 2. Methodologies / Steps

## 3. Findings

## 3. Findings
Images:
- If any "Image Evidence" is present and the provided summaries for the image are available, you may reference them.
- Use a placeholder on its own line where relevant:
#IMAGE_HERE: <image filename or FIGURE id>
- Immediately follow with "Image note:" summarising ONLY what is written in the Image Evidence text.

## 4. Scope
Include lateral movement, privilege escalation, unidentified earlier events, and subsequent relevant events if present.
If not present, say Unknown (not present in the file).

## Impact Assessment
(If applicable based on the provided summaries.)

## Conclusion
Classify as True Positive / False Positive / Benign (based only on provided summaries).
If True Positive, include remediation steps taken (with evidence if possible).

## Next Steps / Call to Action
Include immediate actions and future actions.

## Final Summary
The final summary should be concise but detailed enough to capture the main ideas.
"""

report_manager = FinalReportManager(
    final_report_prompt=FINAL_REPORT_PROMPT,
    report_question_prefix=REPORT_QUESTION_PREFIX
)

chroma_client = chromadb.Client(Settings(anonymized_telemetry=False))


def get_embedding(text):
    return embedding_model.encode(text).tolist()


def chunk_text(text, chunk_size=500):
    words = text.split()
    chunks = []

    for i in range(0, len(words), chunk_size):
        chunk = " ".join(words[i:i + chunk_size])
        chunks.append(chunk)

    return chunks


def read_text_file(file_path, file_name):
    if file_name.lower().endswith(".pdf"):
        reader = PdfReader(file_path)
        text = ""

        for page in reader.pages:
            extracted = page.extract_text()
            if extracted:
                text += extracted + "\n"

        return text

    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()


def get_selected_model_settings():
    ui = cl.user_session.get("chat_settings") or {}
    selected_model = ui.get("LMModel", "qwen/qwen3-vl-4b")

    config = MODEL_CONFIGS[selected_model].copy()
    is_vision_model = config.pop("is_vision", False)

    return config, is_vision_model


@cl.on_chat_start
async def start_chat():
    ui = await cl.ChatSettings(
        [
            Select(
                id="LMModel",
                label="LM Studio Models",
                values=[
                    "qwen/qwen3-vl-4b",
                    "qwen/qwen3-4b",
                    "qwen/qwen3-1.7b",
                ],
                initial_index=0,
            ),
        ]
    ).send()

    cl.user_session.set("chat_settings", ui)

    collection_name = f"documents_{uuid.uuid4().hex}"
    collection = chroma_client.create_collection(name=collection_name)

    cl.user_session.set("current_source", None)
    cl.user_session.set("collection", collection)

    report_manager.init_session()

    await cl.Message(
        content="Attach a file using the paperclip, type your own prompt in the same message, then send."
    ).send()


@cl.on_settings_update
async def setup_agent(settings):
    cl.user_session.set("chat_settings", settings)


@cl.on_message
async def main(message: cl.Message):
    question_text = (message.content or "").strip()
    model_settings, is_vision_model = get_selected_model_settings()

    if report_manager.is_final_report_prompt(question_text):
        await report_manager.handle_final_report(
            question_text,
            client,
            model_settings
        )
        return

    if report_manager.is_report_question_prompt(question_text):
        await report_manager.handle_report_question(
            question_text,
            client,
            model_settings
        )
        return

    if message.elements:
        if question_text == "":
            await cl.Message(
                content="❌ Please type your prompt in the same message as the uploaded file."
            ).send()
            return

        for el in message.elements:
            if hasattr(el, "path") and el.path:
                file_path = el.path
                file_name = getattr(el, "name", "uploaded_file")
                lower = file_name.lower()

                cl.user_session.set("current_source", file_name)

                if lower.endswith((".png", ".jpg", ".jpeg", ".webp")):
                    if not is_vision_model:
                        await cl.Message(
                            content="❌ The selected model does not support image analysis. Please switch to qwen/qwen3-vl-4b."
                        ).send()
                        return

                    status = cl.Message(content=f"Reading `{file_name}`...")
                    await status.send()

                    mime, _ = mimetypes.guess_type(file_path)
                    if mime is None:
                        mime = "image/png"

                    with open(file_path, "rb") as f:
                        b64 = base64.b64encode(f.read()).decode("utf-8")

                    data_url = f"data:{mime};base64,{b64}"

                    image_msg = cl.Message(
                        content="",
                        elements=[cl.Image(path=file_path, name=file_name, display="inline")]
                    )
                    await image_msg.send()

                    text_msg = cl.Message(content="")
                    await text_msg.send()

                    assistant_text = ""
                    stream = await client.chat.completions.create(
                        messages=[
                            {
                                "role": "user",
                                "content": [
                                    {"type": "text", "text": question_text},
                                    {"type": "image_url", "image_url": {"url": data_url}},
                                ],
                            }
                        ],
                        stream=True,
                        **model_settings
                    )

                    async for part in stream:
                        token = part.choices[0].delta.content or ""
                        if token:
                            assistant_text += token
                            await text_msg.stream_token(token)

                    await stream.close()
                    await text_msg.update()

                    report_manager.save_evidence_summary(
                        file_name=file_name,
                        question=question_text,
                        answer=assistant_text,
                        kind="image"
                    )

                    return

                if lower.endswith((".pdf", ".txt", ".md", ".csv")):
                    status = cl.Message(content=f"Indexing `{file_name}`...")
                    await status.send()

                    text = read_text_file(file_path, file_name)
                    chunks = chunk_text(text)
                    collection = cl.user_session.get("collection")
                    upload_stamp = int(time.time() * 1000)

                    for i, chunk in enumerate(chunks):
                        embedding = get_embedding(chunk)
                        collection.add(
                            embeddings=[embedding],
                            documents=[chunk],
                            metadatas=[{"source": file_name, "type": "chunk"}],
                            ids=[f"{file_name}_{upload_stamp}_chunk_{i}"]
                        )

                    status.content = f"✅ Indexed `{file_name}` ({len(chunks)} chunks). Answering your question..."
                    await status.update()
                    break

    collection = cl.user_session.get("collection")
    current_source = cl.user_session.get("current_source")
    if question_text == "":
        await cl.Message(content="❌ Please type your prompt.").send()
        return

    if collection is None:
        await cl.Message(
            content="❌ Attach a file using the paperclip and type your prompt in the same message."
        ).send()
        return

    context_parts = []

    if collection is not None and current_source is not None:
        query_embedding = get_embedding(question_text)
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=20,
            where={"source": current_source}
        )

        docs = results["documents"][0] if results.get("documents") else []

        if len(docs) > 0:
            context_parts.append("\n\n".join(docs))

    context = "\n\n".join(context_parts).strip()

    if context == "":
        await cl.Message(
            content="❌ I could not find context for the current file. Upload a file and ask your question in the same message."
        ).send()
        return

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question_text}"}
    ]

    msg = cl.Message(content="")
    await msg.send()

    full_response = ""
    stream = await client.chat.completions.create(
        messages=messages,
        stream=True,
        **model_settings
    )

    async for part in stream:
        token = part.choices[0].delta.content or ""
        if token:
            full_response += token
            await msg.stream_token(token)

    await stream.close()
    await msg.update()

    report_manager.save_evidence_summary(
        file_name=current_source or "unknown_file",
        question=question_text,
        answer=full_response,
        kind="summary"
    )
