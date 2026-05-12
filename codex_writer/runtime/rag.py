import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class RAGConfig:
    embed_base_url: str = ""
    embed_model: str = ""
    embed_api_key: str = ""
    rerank_base_url: str = ""
    rerank_model: str = ""
    rerank_api_key: str = ""

    @property
    def embedding_configured(self) -> bool:
        """True when embedding credentials are present in the environment."""
        return bool(self.embed_base_url and self.embed_api_key)

    @property
    def rerank_configured(self) -> bool:
        """True when reranker credentials are present in the environment."""
        return bool(self.rerank_base_url and self.rerank_api_key)

    @property
    def mode(self) -> str:
        """Actual search mode that the running code supports.

        The current implementation only provides BM25 search
        (``codex_writer/references/search.py``).  Even if embedding or
        reranker credentials are configured, the retrieval path will still use
        BM25 until a vector/hybrid backend is implemented.  This property is
        intentionally honest so that ``status`` output never claims a
        capability that isn't wired up.

        When a vector backend is added in a future version this method should
        be updated to return ``"vector"`` or ``"hybrid"`` as appropriate.
        """
        return "bm25"

    @property
    def configured_mode(self) -> str:
        """Mode that *would* be active if a vector backend were implemented.

        Useful for roadmap/status messages that want to communicate what
        credentials the author has provided without over-promising search
        quality.
        """
        if self.embedding_configured and self.rerank_configured:
            return "hybrid"
        elif self.embedding_configured:
            return "vector"
        elif self.rerank_configured:
            return "degraded"
        else:
            return "bm25"


def load_rag_config() -> RAGConfig:
    return RAGConfig(
        embed_base_url=os.environ.get("CODEX_WRITER_EMBED_BASE_URL", ""),
        embed_model=os.environ.get("CODEX_WRITER_EMBED_MODEL", ""),
        embed_api_key=os.environ.get("CODEX_WRITER_EMBED_API_KEY", ""),
        rerank_base_url=os.environ.get("CODEX_WRITER_RERANK_BASE_URL", ""),
        rerank_model=os.environ.get("CODEX_WRITER_RERANK_MODEL", ""),
        rerank_api_key=os.environ.get("CODEX_WRITER_RERANK_API_KEY", ""),
    )


def get_search_mode(project_root: Path) -> str:
    """Return the *actual* search mode used at runtime (always ``"bm25"`` for now)."""
    config = load_rag_config()
    return config.mode
