"""Remove the leftover test row from the documents table (exact id, no pattern match)."""
from app import db

TEST_DOC_IDS = ["5f31fca4-27f2-4359-97bc-53b789a625cb"]  # __anon_test__ probe row

for doc_id in TEST_DOC_IDS:
    doc = db.get_document(doc_id)
    if doc is None:
        print(f"already gone: {doc_id}")
        continue
    db.delete_document(doc_id)
    print(f"deleted {doc['filename']} ({doc_id})")

print("remaining documents:", [d["filename"] for d in db.list_documents()])
print("chunk count:", db.count_chunks())
