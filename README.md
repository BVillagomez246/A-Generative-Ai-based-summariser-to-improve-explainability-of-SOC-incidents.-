# A-Generative-Ai-based-summariser-to-improve-explainability-of-SOC-incidents.-
## Project Overview

This project is a SOC investigation assistant built with **Chainlit** as the user interface. It is designed to support security analysts during incident investigations by making it easier to upload, review, query, and summarise different types of cybersecurity evidence in one workflow. The application can handle evidence such as security logs, MITRE-related event data, file integrity monitoring data, and images used for visualisation or investigation context.

For text-based evidence, the system uses a **Retrieval-Augmented Generation (RAG)** approach. When files such as `.pdf`, `.txt`, `.md`, or `.csv` are uploaded, their contents are extracted and split into smaller **chunks** so that large documents can be processed more effectively. These chunks are then converted into **embedding vectors**, which are numerical representations of the text, and stored in a vector database. This allows the application to retrieve the most relevant parts of the uploaded evidence when a user asks a question, rather than relying on the full document every time.

When a question is submitted, the application searches the stored vectors to find the most relevant chunks from the current uploaded file. These retrieved chunks are then passed to the language model as context, allowing it to generate a grounded response based only on the uploaded evidence. This helps reduce unsupported answers and keeps the output focused on the investigation material provided by the user.

The project also supports image-based evidence. Images can be uploaded for visual analysis, and the model can generate responses based on the image and the user’s prompt. These outputs are treated as part of the investigation evidence in the same way as text-based responses, allowing both textual and visual findings to contribute to the overall case.

A key feature of the system is that generated responses are stored in `evidence_summaries` throughout the investigation process. This means the application does not only answer one question at a time, but also builds up a collection of findings as the analyst works through the evidence. This supports a more realistic SOC workflow, where multiple pieces of evidence are reviewed over time before a final conclusion is written.

When the user enters `FINAL REPORT`, the application uses all stored findings in `evidence_summaries` to generate a complete investigation report. This report is intended to summarise the overall incident using the accumulated evidence gathered during the session. After the report has been created, the `REPORT QUESTION:` trigger allows the user to ask follow-up questions based only on the generated report, making it easier to review conclusions, confirm details, and quickly revisit important findings without manually searching through the original outputs again.

Overall, the project is designed to reduce the manual effort involved in reviewing evidence and writing investigation reports. By combining a **Chainlit interface**, a **RAG pipeline**, **chunking**, **embedding-based retrieval**, and report generation based on accumulated evidence, the system aims to support SOC analysts with a more efficient and structured investigation workflow.

## Attacks Used

The investigation scenarios used in this project were based on **two phishing and privilege escalation attacks carried out on Windows OS and Ubuntu virtual machines**, as well as **one brute force attack carried out on an Ubuntu virtual machine**.
