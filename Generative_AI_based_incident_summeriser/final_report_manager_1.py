import chainlit as cl


# This class handles: 1. Saving evidence summaries, 2. Building the final report context, 3. Generating the final report, 
# 4. Answering follow-up questions about the final report
class FinalReportManager:
    def __init__(self, final_report_prompt, report_question_prefix="REPORT QUESTION:"):
        self.final_report_prompt = final_report_prompt
        self.report_question_prefix = report_question_prefix

    # Create session state variables when the app starts
    def init_session(self):
        cl.user_session.set("evidence_summaries", [])
        cl.user_session.set("final_report_text", "")

    # Check whether the user typed FINAL REPORT
    def is_final_report_prompt(self, text):
        if not text:
            return False
        return text.strip().upper().startswith("FINAL REPORT")

    # Check whether the user typed REPORT QUESTION:
    def is_report_question_prompt(self, text):
        if not text:
            return False
        return text.strip().upper().startswith(self.report_question_prefix)

    # Save one answer into the evidence list
    # This is what later gets combined into the final report
    def save_evidence_summary(self, file_name, question, answer, kind="summary"):
        evidence = cl.user_session.get("evidence_summaries") or []
        evidence.append({
            "file_name": file_name,
            "question": question,
            "answer": answer,
            "kind": kind,
        })
        cl.user_session.set("evidence_summaries", evidence)

    # Build one large text block from all saved evidence summaries
    def build_context(self):
        evidence = cl.user_session.get("evidence_summaries") or []

        if not evidence:
            return ""

        parts = []
        for i, item in enumerate(evidence, start=1):
            block = (
                f"Summary {i}\n"
                f"File: {item['file_name']}\n"
                f"Type: {item['kind']}\n"
                f"Question: {item['question']}\n"
                f"Answer:\n{item['answer']}"
            )
            parts.append(block)

        return "\n\n".join(parts)

    # Reusable function to stream model output to Chainlit
    async def stream_response(self, messages, client, used_settings):
        msg = cl.Message(content="")
        await msg.send()

        full_response = ""

        stream = await client.chat.completions.create(
            messages=messages,
            stream=True,
            **used_settings
        )

        async for part in stream:
            token = part.choices[0].delta.content or ""
            if token:
                full_response += token
                await msg.stream_token(token)

        await stream.close()
        await msg.update()
        return full_response

    # Generate the final report from all saved evidence
    async def handle_final_report(self, question_text, client, used_settings):
        context = self.build_context()

        if not context:
            await cl.Message(
                content="❌ No saved summaries yet. Upload files first and ask questions before generating the final report."
            ).send()
            return

        # If the user typed only FINAL REPORT, use the default report template
        if question_text.strip().upper() == "FINAL REPORT":
            report_prompt = self.final_report_prompt
        else:
            report_prompt = question_text

        messages = [
            {
                "role": "system",
                "content": "You are an expert SOC analyst. Use ONLY the provided summaries. Do not invent missing evidence."
            },
            {
                "role": "user",
                "content": f"Provided summaries:\n\n{context}\n\n{report_prompt}"
            }
        ]

        # Use unlimited output length for the final report
        report_settings = {**used_settings, "max_tokens": -1}
        full_response = await self.stream_response(messages, client, report_settings)

        # Save the final report text so it can be queried later
        cl.user_session.set("final_report_text", full_response)

    # Answer questions about the already generated final report
    async def handle_report_question(self, question_text, client, used_settings):
        final_report = cl.user_session.get("final_report_text") or ""

        if not final_report.strip():
            await cl.Message(
                content="❌ No final report found yet. Generate the final report first by typing FINAL REPORT."
            ).send()
            return

        report_question = question_text[len(self.report_question_prefix):].strip()

        if not report_question:
            await cl.Message(
                content="❌ Please type your question after REPORT QUESTION:"
            ).send()
            return

        messages = [
            {
                "role": "system",
                "content": (
                    "Answer using ONLY the saved final report below. "
                    "Do not use outside knowledge. "
                    "Do not guess or fill gaps. "
                    "If the answer is not clearly supported by the report, say: Not found in the report."
                )
            },
            {
                "role": "user",
                "content": f"Final report:\n\n{final_report}\n\nQuestion: {report_question}"
            }
        ]

        await self.stream_response(messages, client, used_settings)