# ONNX embedding bundle (`all-MiniLM-L6-v2`)

TinySearch uses this folder when `model.onnx` and tokenizer files are present: pooled
sentence embeddings compatible with `sentence-transformers/all-MiniLM-L6-v2`, with a
much faster cold start than loading PyTorch inside `SentenceTransformer`.

## Automatic download

When `embedding_backend` in `configs/research_config.json` is `onnx` and
`embedding_model` is `fast`, starting **`servers/mcp_server.py`** or
**`servers/fastapi_server.py`** downloads the bundle once from Hugging Face
(`onnx-models/all-MiniLM-L6-v2-onnx`) into this directory. The model is
**Apache-2.0** — keep attribution when redistributing these files.

Override the directory with `TINYSEARCH_ONNX_MODEL_DIR` if needed.

## Manual export (optional)

From the repo root, with `onnx` installed for export (`pip install onnx`):

```bash
python scripts/export_embedding_onnx.py
```

This pulls weights from `sentence-transformers/all-MiniLM-L6-v2`, then writes
`model.onnx` (~90 MB) plus tokenizer artifacts here using PyTorch. Inference still uses
`onnxruntime` only.

## Override path

Set `TINYSEARCH_ONNX_MODEL_DIR` to an absolute directory that contains the same layout:
`model.onnx`, `tokenizer.json`, plus companion tokenizer files as shipped by the repos above.
