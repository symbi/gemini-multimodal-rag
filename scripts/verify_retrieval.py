"""Verify retrieval quality across modalities (no Codex — retrieval only)."""
from app import retrieval

CASES = [
    ("What was Q3 revenue and gross margin?", None),
    ("What is the payload and price of the Atlas arm?", None),
    ("a robotic arm drawing with reach and payload labels", "image"),
    ("What is the emergency stop time?", None),
    ("how many pizzas were ordered for the retro?", None),
]

for question, modality in CASES:
    chunks = retrieval.search(question, top_k=3, modality=modality)
    print(f"\nQ: {question}" + (f"  [modality={modality}]" if modality else ""))
    for i, c in enumerate(chunks, 1):
        sim = c.get("similarity")
        sim_s = f"{sim:.4f}" if isinstance(sim, (int, float)) else "?"
        preview = (c.get("content_text") or "")[:70].replace("\n", " ")
        print(f"   [{i}] {c['filename']:26} {c['modality']:5} sim={sim_s}  {preview}")
