from app.services.document_ingestion import chunk_text


def test_chunk_text_uses_overlap():
    text = " ".join(f"word{i}" for i in range(120))
    chunks = chunk_text(text, max_words=50, overlap_words=10)

    assert len(chunks) == 3
    assert chunks[0].split()[-10:] == chunks[1].split()[:10]
    assert chunks[1].split()[-10:] == chunks[2].split()[:10]


def test_chunk_text_empty_input():
    assert chunk_text("") == []
