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


# Connect to your local LM Studio server
client = AsyncOpenAI(api_key="lm-studio", base_url="http://127.0.0.1:1234/v1")

# Load the embedding model used to turn text into vectors for retrieval
embedding_model = SentenceTransformer("all-MiniLM-L6-v2")


# Store the available models the user can choose from in the Chainlit UI
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


# System prompt for normal file question-answering
SYSTEM_PROMPT = "You are a helpful assistant. Answer questions based only on the provided context."


# Prompt template used when generating the final investigation report
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


# Create the report manager that handles FINAL REPORT and REPORT QUESTION logic
report_manager = FinalReportManager(
    final_report_prompt=FINAL_REPORT_PROMPT
)


# Start ChromaDB locally and disable telemetry
chroma_client = chromadb.Client(Settings(anonymized_telemetry=False))


# Convert a piece of text into an embedding vector
def get_embedding(text):
    return embedding_model.encode(text).tolist()


# Split large text into smaller chunks before storing in ChromaDB
def chunk_text(text, chunk_size=500):
    words = text.split()
    chunks = []

    for i in range(0, len(words), chunk_size):
        chunk = " ".join(words[i:i + chunk_size])
        chunks.append(chunk)

    return chunks


# Read file contents
# - PDF files are read page by page
# - txt, md, csv files are read normally as text
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


# Get the model currently selected by the user from Chainlit settings
def get_selected_model_settings():
    ui = cl.user_session.get("chat_settings") or {}
    selected_model = ui.get("LMModel", "qwen/qwen3-vl-4b")

    config = MODEL_CONFIGS[selected_model].copy()
    is_vision_model = config.pop("is_vision", False)

    return config, is_vision_model


# Runs once when the chat starts
# Sets up the model dropdown, Chroma collection, and report session state
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


# Update the saved settings if the user changes model in the UI
@cl.on_settings_update
async def setup_agent(settings):
    cl.user_session.set("chat_settings", settings)

# Main message handler
# Controls:# 1. FINAL REPORT requests, # 2. REPORT QUESTION requests, # 3. File uploads, # 4. Normal Q&A on the current uploaded file
@cl.on_message
async def main(message: cl.Message):
    question_text = (message.content or "").strip()
    model_settings, is_vision_model = get_selected_model_settings()

    # Check if the user is asking for the final report
    if report_manager.is_final_report_prompt(question_text):
        await report_manager.handle_final_report(
            question_text,
            client,
            model_settings
        )
        return

    # Check if the user is asking a question about an already generated report
    if report_manager.is_report_question_prompt(question_text):
        await report_manager.handle_report_question(
            question_text,
            client,
            model_settings
        )
        return

    # Handle uploaded files
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

                # Save which file is the current one, so later questions use this file only
                cl.user_session.set("current_source", file_name)

                # Handle image uploads
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

                    # Show the uploaded image in the chat
                    image_msg = cl.Message(
                        content="",
                        elements=[cl.Image(path=file_path, name=file_name, display="inline")]
                    )
                    await image_msg.send()

                    # Stream the model's answer below the image
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

                    # Save the image analysis output for later final report generation
                    report_manager.save_evidence_summary(
                        file_name=file_name,
                        question=question_text,
                        answer=assistant_text,
                        kind="image"
                    )

                    return

                # Handle text-based files
                if lower.endswith((".pdf", ".txt", ".md", ".csv")):
                    status = cl.Message(content=f"Indexing `{file_name}`...")
                    await status.send()

                    text = read_text_file(file_path, file_name)
                    chunks = chunk_text(text)
                    collection = cl.user_session.get("collection")
                    upload_stamp = int(time.time() * 1000)

                    # Store each chunk and its embedding in ChromaDB
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

    # After indexing or on later questions, get the stored collection and current file
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

    # Retrieve relevant chunks only from the current uploaded file
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

    # Build the prompt for normal file-based question answering
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question_text}"}
    ]

    # Stream the final answer back to the user
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

    # Save the normal answer as evidence for the final report later
    report_manager.save_evidence_summary(
        file_name=current_source or "unknown_file",
        question=question_text,
        answer=full_response,
        kind="summary"
    )