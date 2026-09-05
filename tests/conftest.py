import pytest


@pytest.fixture(autouse=True)
def offline_document_embeddings(monkeypatch):
    """Default tests never call Ollama for passage embeddings."""

    def fake(texts, **kwargs):
        return [[float(len(text)), 1.0, 0.25] for text in texts]

    monkeypatch.setattr("wsf.draft.ollama_embed", fake)
    monkeypatch.setattr("wsf.document_index.ollama_embed", fake)
