"""Download and persist the MiniLM ONNX bundle under ``embedding_service._onnx_bundle_dir()``."""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

from huggingface_hub import snapshot_download

from services.embedding_service import (
    _onnx_bundle_dir,
    _onnx_bundle_ready,
    clear_onnx_runtime_cache,
)
from services.onnx_bundle_constants import (
    MINILM_ONNX_BUNDLE_ALLOW_PATTERNS,
    MINILM_ONNX_BUNDLE_REPO_ID,
)

_LOCK_NAME = ".download.lock"
_STALE_LOCK_SEC = 1800.0
_LOCK_WAIT_SEC = 3600.0
_POLL_SEC = 0.25


@contextmanager
def _exclusive_bundle_lock(bundle_dir: Path):
    """Serialize concurrent downloads into ``bundle_dir`` (cross-process)."""
    bundle_dir.mkdir(parents=True, exist_ok=True)
    lock_path = bundle_dir / _LOCK_NAME
    deadline = time.monotonic() + _LOCK_WAIT_SEC
    while True:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            break
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"timed out waiting for ONNX bundle lock {lock_path}"
                ) from None
            try:
                age = time.time() - lock_path.stat().st_mtime
                if age > _STALE_LOCK_SEC:
                    lock_path.unlink(missing_ok=True)
                    continue
            except OSError:
                pass
            time.sleep(_POLL_SEC)
    try:
        yield
    finally:
        lock_path.unlink(missing_ok=True)


def ensure_onnx_bundle_sync() -> None:
    """If the ONNX bundle is missing, download it once into the bundle directory."""
    if _onnx_bundle_ready():
        return

    dest = _onnx_bundle_dir()
    with _exclusive_bundle_lock(dest):
        if _onnx_bundle_ready():
            return

        print(
            "[tinysearch] downloading ONNX embedding bundle "
            f"({MINILM_ONNX_BUNDLE_REPO_ID}); model license: Apache-2.0 "
            "(see Hugging Face model card). One-time fetch.",
            file=sys.stderr,
            flush=True,
        )

        dest.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="tinysearch-onnx-dl-") as td_raw:
            td = Path(td_raw)
            snapshot_download(
                repo_id=MINILM_ONNX_BUNDLE_REPO_ID,
                local_dir=str(td),
                local_dir_use_symlinks=False,
                allow_patterns=list(MINILM_ONNX_BUNDLE_ALLOW_PATTERNS),
            )
            missing = [
                name
                for name in MINILM_ONNX_BUNDLE_ALLOW_PATTERNS
                if not (td / name).is_file()
            ]
            if missing:
                raise RuntimeError(
                    "ONNX bundle download incomplete; missing: "
                    + ", ".join(sorted(missing))
                )
            for name in MINILM_ONNX_BUNDLE_ALLOW_PATTERNS:
                shutil.copy2(td / name, dest / name)

        if not _onnx_bundle_ready():
            raise RuntimeError(
                f"ONNX bundle still incomplete after download under {dest}"
            )

    clear_onnx_runtime_cache()
