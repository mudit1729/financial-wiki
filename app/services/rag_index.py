from app.models import DocumentChunk
from app.services.agent_prompts import list_agent_prompt_templates


def index_status():
    return {
        "chunk_count": DocumentChunk.query.count(),
        "document_count": len({row.document_id for row in DocumentChunk.query.with_entities(DocumentChunk.document_id).all()}),
        "retrieval_engine": "hybrid-keyword-tfidf-local",
        "answer_provider": "local-extractive",
        "agent_prompt_template_count": len(list_agent_prompt_templates()),
    }
