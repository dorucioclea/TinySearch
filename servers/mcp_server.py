from __future__ import annotations

import os
import sys
import time
import faulthandler
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from mcp.server.fastmcp import FastMCP

from pipelines.agentic_research import agentic_run
from services.embedding_service import normalize_embedding_backend
from services.research_config_service import (
    config_trace_path,
    load_research_config,
    research_run_kwargs,
    research_tokenizer_name,
)
from services.token_counter_service import token_count


def _mcp_host() -> str:
    return os.environ.get("MCP_HOST", "127.0.0.1").strip() or "127.0.0.1"


def _mcp_port() -> int:
    raw = os.environ.get("MCP_PORT", "8000").strip()
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError("MCP_PORT must be an integer") from exc


MCP_INSTRUCTIONS = """
This MCP server exposes one high-level web research tool:

1. research(query)

Pass the user's question as-is in query. Do not rewrite, correct spelling,
expand abbreviations, add dates, add missing context, simplify, translate, or
otherwise improve the user's wording before calling the tool.

The tool searches DuckDuckGo, ranks search results with dense embeddings and
BM25 using reciprocal rank fusion, crawls kept pages, ranks page chunks, and
returns a prompt in the answer field. The caller's LLM should answer from that
prompt and cite source URLs from the result blocks.
""".strip()


def _research_settings() -> dict[str, Any]:
    return research_run_kwargs(load_research_config())


def _answer_tokens(answer: str) -> int:
    return token_count(answer, encoding_name=research_tokenizer_name())


def _ensure_local_bundle_for_config(config: dict[str, Any]) -> None:
    if normalize_embedding_backend(str(config["embedding_backend"])) != "onnx":
        return
    from services.onnx_bundle_service import ensure_onnx_bundle_sync

    ensure_onnx_bundle_sync(str(config["embedding_model"]))


def _validate_query(query: str) -> str:
    query = query.strip()
    if not query:
        raise ValueError("query must not be empty")
    return query


def _log(message: str) -> None:
    print(f"[tinysearch] {message}", file=sys.stderr, flush=True)


def _enable_traceback_dump() -> None:
    raw = os.environ.get("TINYSEARCH_DUMP_TRACEBACK_AFTER", "").strip()
    if not raw:
        return
    try:
        delay = max(1.0, float(raw))
    except ValueError:
        delay = 30.0
    faulthandler.enable(file=sys.stderr, all_threads=True)
    faulthandler.dump_traceback_later(delay, repeat=True, file=sys.stderr)


mcp = FastMCP(
    "tinysearch",
    instructions=MCP_INSTRUCTIONS,
    host=_mcp_host(),
    port=_mcp_port(),
)


@mcp.tool(
    name="research",
    title="Research",
    description=(
        "Search the web, crawl ranked pages, and return a grounded answer prompt. "
        "Input schema has exactly one field: query. Pass the user's question as-is."
    ),
)
async def research(query: str) -> dict[str, Any]:
    query = _validate_query(query)
    started = time.monotonic()
    _log(f"research called query={query!r}")
    try:
        result = await agentic_run(
            query,
            trace_path=config_trace_path(),
            **_research_settings(),
        )
        elapsed = time.monotonic() - started
        _log(
            "research returning "
            f"answer_tokens={_answer_tokens(result.answer)} "
            f"elapsed={elapsed:.2f}s"
        )
        return {"answer": result.answer}
    except Exception as exc:
        elapsed = time.monotonic() - started
        _log(f"research failed elapsed={elapsed:.2f}s error={exc!r}")
        raise


if __name__ == "__main__":
    _enable_traceback_dump()
    cfg = load_research_config()
    _ensure_local_bundle_for_config(cfg)
    transport = os.environ.get("MCP_TRANSPORT", "stdio").strip() or "stdio"
    if transport not in {"stdio", "sse", "streamable-http"}:
        raise ValueError(
            "MCP_TRANSPORT must be one of: stdio, sse, streamable-http "
            "(default stdio for IDE-spawned MCP; set env only for standalone HTTP/SSE)"
        )
    mcp.run(transport=transport)
