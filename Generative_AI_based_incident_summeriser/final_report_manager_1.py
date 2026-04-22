import chainlit as cl


class FinalReportManager:
    def __init__(self, final_report_prompt, report_question_prefix="REPORT QUESTION:"):
        self.final_report_prompt = final_report_prompt
        self.report_question_prefix = report_question_prefix

    def init_session(self):
        cl.user_session.set("evidence_summaries", [])
        cl.user_session.set("final_report_text", "")

    def is_final_report_prompt(self, text):
        if not text:
            return False
        return text.strip().upper().startswith("FINAL REPORT")

    def is_report_question_prompt(self, text):
        if not text:
            return False
        return text.strip().upper().startswith(self.report_question_prefix)

    def save_evidence_summary(self, file_name, question, answer, kind="summary"):
        evidence = cl.user_session.get("evidence_summaries") or []
        evidence.append({
            "file_name": file_name,
            "question": question,
            "answer": answer,
            "kind": kind,
        })
        cl.user_session.set("evidence_summaries", evidence)

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

    async def handle_final_report(self, question_text, client, used_settings):
        context = self.build_context()

        if not context:
            await cl.Message(
                content="❌ No saved summaries yet. Upload files first and ask questions before generating the final report."
            ).send()
            return True

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

        report_settings = {**used_settings, "max_tokens": -1}
        full_response = await self.stream_response(messages, client, report_settings)

        cl.user_session.set("final_report_text", full_response)


        return True

    async def handle_report_question(self, question_text, client, used_settings):
        final_report = cl.user_session.get("final_report_text") or ""

        if not final_report.strip():
            await cl.Message(
                content="❌ No final report found yet. Generate the final report first by typing FINAL REPORT."
            ).send()
            return True

        report_question = question_text[len(self.report_question_prefix):].strip()

        if not report_question:
            await cl.Message(
                content="❌ Please type your question after REPORT QUESTION:"
            ).send()
            return True

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


        return True
