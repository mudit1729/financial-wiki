from app.models import DocumentChunk


def index_status():
    return {
        "chunk_count": DocumentChunk.query.count(),
        "document_count": len({row.document_id for row in DocumentChunk.query.with_entities(DocumentChunk.document_id).all()}),
    }
