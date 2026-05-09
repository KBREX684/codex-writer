import os
from codex_writer.runtime.rag import load_rag_config, get_search_mode


def test_rag_defaults_to_bm25_without_config(monkeypatch):
    monkeypatch.delenv("CODEX_WRITER_EMBED_API_KEY", raising=False)
    monkeypatch.delenv("CODEX_WRITER_EMBED_BASE_URL", raising=False)
    monkeypatch.delenv("CODEX_WRITER_RERANK_API_KEY", raising=False)
    config = load_rag_config()
    assert config.embedding_available is False
    assert config.rerank_available is False
    assert config.mode == "bm25"


def test_rag_hybrid_when_all_configured(monkeypatch):
    monkeypatch.setenv("CODEX_WRITER_EMBED_BASE_URL", "http://localhost:8080")
    monkeypatch.setenv("CODEX_WRITER_EMBED_API_KEY", "test-key")
    monkeypatch.setenv("CODEX_WRITER_RERANK_BASE_URL", "http://localhost:8081")
    monkeypatch.setenv("CODEX_WRITER_RERANK_API_KEY", "test-key")
    config = load_rag_config()
    assert config.mode == "hybrid"


def test_rag_vector_when_only_embed_configured(monkeypatch):
    monkeypatch.setenv("CODEX_WRITER_EMBED_BASE_URL", "http://localhost:8080")
    monkeypatch.setenv("CODEX_WRITER_EMBED_API_KEY", "test-key")
    monkeypatch.delenv("CODEX_WRITER_RERANK_API_KEY", raising=False)
    config = load_rag_config()
    assert config.mode == "vector"


def test_rag_mode_integrated_into_search(tmp_path):
    mode = get_search_mode(tmp_path)
    assert mode in ("bm25", "vector", "hybrid", "degraded")
