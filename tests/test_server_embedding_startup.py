from __future__ import annotations

import unittest
from unittest.mock import patch

from servers.fastapi_server import _ensure_local_bundle_for_config as ensure_fastapi_bundle
from servers.mcp_server import _ensure_local_bundle_for_config as ensure_mcp_bundle


class ServerEmbeddingStartupTests(unittest.IsolatedAsyncioTestCase):
    async def test_fastapi_startup_ensures_selected_local_embedding_model(self) -> None:
        cfg = {"embedding_backend": "onnx", "embedding_model": "balanced"}

        with patch("services.onnx_bundle_service.ensure_onnx_bundle_sync") as ensure:
            await ensure_fastapi_bundle(cfg)

        ensure.assert_called_once_with("balanced")

    async def test_fastapi_startup_skips_openai_compatible_backend(self) -> None:
        cfg = {"embedding_backend": "openai_compatible", "embedding_model": "balanced"}

        with patch("services.onnx_bundle_service.ensure_onnx_bundle_sync") as ensure:
            await ensure_fastapi_bundle(cfg)

        ensure.assert_not_called()


class McpEmbeddingStartupTests(unittest.TestCase):
    def test_mcp_startup_ensures_selected_local_embedding_model(self) -> None:
        cfg = {"embedding_backend": "onnx", "embedding_model": "quality"}

        with patch("services.onnx_bundle_service.ensure_onnx_bundle_sync") as ensure:
            ensure_mcp_bundle(cfg)

        ensure.assert_called_once_with("quality")

    def test_mcp_startup_skips_openai_compatible_backend(self) -> None:
        cfg = {"embedding_backend": "openai_compatible", "embedding_model": "quality"}

        with patch("services.onnx_bundle_service.ensure_onnx_bundle_sync") as ensure:
            ensure_mcp_bundle(cfg)

        ensure.assert_not_called()


if __name__ == "__main__":
    unittest.main()
