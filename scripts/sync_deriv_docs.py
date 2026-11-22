"""Automated downloader and integrity verifier for official Deriv API docs (developers.deriv.com)."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
import urllib.error
import urllib.request
from urllib.parse import urlparse

OFFICIAL_HOSTS = {"developers.deriv.com", "api.derivws.com"}
LLMS_TXT_URL = "https://developers.deriv.com/llms.txt"
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent.parent / "docs" / "vendor" / "deriv-api"

URL_RE = re.compile(r"https?://[^\s\)\]>\"']+")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fetch_url(url: str, timeout: int = 20) -> bytes:
    parsed = urlparse(url)
    if parsed.hostname not in OFFICIAL_HOSTS:
        raise ValueError(f"Host nao oficial bloqueado: {parsed.hostname}")
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Prado-Ubuntu-HFT-DocSync/1.0"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read()
    if not data or not data.strip():
        raise ValueError(f"Resposta vazia para {url}")
    return data


def extract_urls(text: str) -> list[str]:
    seen: set[str] = set()
    urls: list[str] = []
    for raw in URL_RE.findall(text):
        clean = raw.rstrip(".,;:")
        parsed = urlparse(clean)
        if parsed.hostname not in OFFICIAL_HOSTS:
            continue
        if clean not in seen:
            seen.add(clean)
            urls.append(clean)
    return urls


def target_relpath_for_url(url: str) -> Path | None:
    parsed = urlparse(url)
    path = parsed.path.lstrip("/")
    if url == LLMS_TXT_URL or path == "llms.txt":
        return Path("llms.txt")
    if path.startswith("llms/") and path.endswith(".md"):
        return Path(path)
    if path.endswith(".json") or "/schemas/" in path or "schema" in path.lower():
        name = Path(path).name or "schema.json"
        if not name.endswith(".json"):
            name += ".json"
        return Path("schemas") / name
    return None


def safe_write(dest: Path, data: bytes) -> None:
    if not data or not data.strip():
        raise ValueError(f"Recusando sobrescrever {dest} com conteudo vazio")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)


def sync_docs(
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    fetcher=fetch_url,
) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    llms_bytes = fetcher(LLMS_TXT_URL)
    safe_write(output_dir / "llms.txt", llms_bytes)
    llms_text = llms_bytes.decode("utf-8", errors="replace")

    discovered = extract_urls(llms_text)
    files_manifest: list[dict] = [
        {
            "path": "llms.txt",
            "url": LLMS_TXT_URL,
            "sha256": sha256_bytes(llms_bytes),
            "bytes": len(llms_bytes),
            "kind": "index",
        }
    ]
    failures: list[dict] = []
    processed: set[str] = {LLMS_TXT_URL}
    queue: list[str] = list(discovered)

    while queue:
        url = queue.pop(0)
        if url in processed:
            continue
        processed.add(url)
        rel = target_relpath_for_url(url)
        if rel is None:
            continue
        try:
            data = fetcher(url)
            dest = output_dir / rel
            safe_write(dest, data)
            kind = "schema" if rel.parts[0] == "schemas" else "markdown"
            files_manifest.append(
                {
                    "path": rel.as_posix(),
                    "url": url,
                    "sha256": sha256_bytes(data),
                    "bytes": len(data),
                    "kind": kind,
                }
            )
            if kind == "markdown":
                text = data.decode("utf-8", errors="replace")
                for nested in extract_urls(text):
                    if nested not in processed and target_relpath_for_url(nested) is not None:
                        queue.append(nested)
        except Exception as exc:
            failures.append({"url": url, "error": str(exc)})

    manifest = {
        "source": LLMS_TXT_URL,
        "synced_at": datetime.now(timezone.utc).isoformat(),
        "total_files": len(files_manifest),
        "markdown_count": sum(1 for f in files_manifest if f["kind"] == "markdown"),
        "schema_count": sum(1 for f in files_manifest if f["kind"] == "schema"),
        "failures": failures,
        "files": files_manifest,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return manifest


def verify_manifest(output_dir: Path = DEFAULT_OUTPUT_DIR) -> tuple[bool, list[str]]:
    manifest_path = output_dir / "manifest.json"
    if not manifest_path.exists():
        return False, ["manifest.json nao encontrado"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    errors: list[str] = []
    for entry in manifest.get("files", []):
        fpath = output_dir / entry["path"]
        if not fpath.exists():
            errors.append(f"Arquivo ausente: {entry['path']}")
            continue
        actual_hash = sha256_bytes(fpath.read_bytes())
        if actual_hash != entry["sha256"]:
            errors.append(f"SHA-256 divergente em {entry['path']}")
    return len(errors) == 0, errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync Deriv API official docs")
    parser.add_argument("--verify", action="store_true", help="Verify SHA-256 against manifest.json")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    if args.verify:
        ok, errs = verify_manifest(args.output_dir)
        if ok:
            print("Manifest integrity OK.")
            return 0
        for e in errs:
            print(f"ERROR: {e}", file=sys.stderr)
        return 1

    manifest = sync_docs(args.output_dir)
    print(
        f"Synced {manifest['total_files']} files "
        f"(markdown={manifest['markdown_count']}, schemas={manifest['schema_count']}, "
        f"failures={len(manifest['failures'])})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
