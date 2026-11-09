"""Print the current index state (documents + chunk counts)."""
from app import db

docs = db.list_documents()
print(f"{len(docs)} document(s), {db.count_chunks()} chunk(s) total\n")
for d in docs:
    err = f"  ERROR: {d['error']}" if d.get("error") else ""
    print(f"  {d['filename']:28} {d['modality']:6} {d['status']:10} "
          f"chunks={d['chunk_count']}{err}")
