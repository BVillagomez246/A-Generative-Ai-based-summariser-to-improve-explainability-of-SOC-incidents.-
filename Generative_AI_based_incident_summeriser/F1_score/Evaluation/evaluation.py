import evaluate

bertscore = evaluate.load("bertscore")

with open("ubuntu_phishing_report.txt", "r", encoding="utf-8") as f:
    llm_output = f.read()

with open("human_ubuntu_phishing_report.txt", "r", encoding="utf-8") as f:
    human_reference = f.read()

results = bertscore.compute(
    predictions=[llm_output],
    references=[human_reference],
    lang="en"
)

print("BERTScore Precision:", results["precision"][0])
print("BERTScore Recall:", results["recall"][0])
print("BERTScore F1:", results["f1"][0])