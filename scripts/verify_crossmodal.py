"""Verify cross-modal retrieval: text queries matching media chunks."""
from app import retrieval

CASES = [
    ("a video demo of the robotic arm showing reach and payload", None),
    ("what does the audio recording sound like", None),
    ("what is the payload and price of the Atlas arm", None),
    ("emergency stop response time in milliseconds", None),
]

for question, modality in CASES:
    chunks = retrieval.search(question, top_k=3, modality=modality)
    print(f"\nQ: {question}")
    for i, c in enumerate(chunks, 1):
        sim = c.get("similarity")
        sim_s = f"{sim:.4f}" if isinstance(sim, (int, float)) else "?"
        preview = (c.get("content_text") or "")[:60].replace("\n", " ")
        print(f"   [{i}] {c['filename']:24} {c['modality']:5} sim={sim_s}  {preview}")
