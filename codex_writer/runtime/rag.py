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
    def embedding_available(self) -> bool:
        return bool(self.embed_base_url and self.embed_api_key)

    @property
    def rerank_available(self) -> bool:
        return bool(self.rerank_base_url and self.rerank_api_key)

    @property
    def mode(self) -> str:
        if self.embedding_available and self.rerank_available:
            return "hybrid"
        elif self.embedding_available:
            return "vector"
        elif self.rerank_available:
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
    config = load_rag_config()
    return config.mode
