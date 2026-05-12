import os
from codex_writer.runtime.rag import load_rag_config, get_search_mode


def test_rag_defaults_to_bm25_without_config(monkeypatch):
    monkeypatch.delenv("CODEX_WRITER_EMBED_API_KEY", raising=False)
    monkeypatch.delenv("CODEX_WRITER_EMBED_BASE_URL", raising=False)
    monkeypatch.delenv("CODEX_WRITER_RERANK_API_KEY", raising=False)
    config = load_rag_config()
    # With no credentials, both configured_mode and mode should report bm25.
    assert config.embedding_configured is False
    assert config.rerank_configured is False
    assert config.mode == "bm25"
    assert config.configured_mode == "bm25"


def test_rag_configured_mode_hybrid_when_all_configured(monkeypatch):
    """When embedding + reranker creds are set, configured_mode reports 'hybrid'.

    Note: the *actual* search mode (``config.mode``) remains ``"bm25"`` until a
    vector backend is implemented.  This test validates the honest distinction
    between configured credentials and running implementation.
    """
    monkeypatch.setenv("CODEX_WRITER_EMBED_BASE_URL", "http://localhost:8080")
    monkeypatch.setenv("CODEX_WRITER_EMBED_API_KEY", "test-key")
    monkeypatch.setenv("CODEX_WRITER_RERANK_BASE_URL", "http://localhost:8081")
    monkeypatch.setenv("CODEX_WRITER_RERANK_API_KEY", "test-key")
    config = load_rag_config()
    assert config.configured_mode == "hybrid"
    # Actual runtime mode is still bm25 (vector backend not yet implemented).
    assert config.mode == "bm25"


def test_rag_configured_mode_vector_when_only_embed_configured(monkeypatch):
    """When only embedding creds are set, configured_mode reports 'vector'."""
    monkeypatch.setenv("CODEX_WRITER_EMBED_BASE_URL", "http://localhost:8080")
    monkeypatch.setenv("CODEX_WRITER_EMBED_API_KEY", "test-key")
    monkeypatch.delenv("CODEX_WRITER_RERANK_API_KEY", raising=False)
    config = load_rag_config()
    assert config.configured_mode == "vector"
    assert config.mode == "bm25"


def test_rag_mode_integrated_into_search(tmp_path):
    mode = get_search_mode(tmp_path)
    assert mode == "bm25"
