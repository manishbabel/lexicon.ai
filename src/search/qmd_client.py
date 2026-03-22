"""QMD client — on-device hybrid search via CLI subprocess.

QMD (by Tobi Lütke) provides BM25 + vector + LLM rerank using local GGUF models.
All search runs on-device with zero API costs.

CLI reference:
  qmd query <text>           — hybrid search (BM25 + vector + rerank)
  qmd search <text>          — BM25 keyword search only
  qmd get <file>             — get a single document
  qmd collection add <path>  — add a collection
  qmd update                 — re-index collections
  qmd embed                  — generate/refresh embeddings

Usage:
    client = QMDClient(collection="lexicon")
    results = await client.query("retrieval augmented generation", n=5)
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
from pathlib import Path
from typing import Any

from src.shared.constants import VAULT_DIR
from src.shared.logger import get_logger

logger = get_logger("lexicon.search.qmd")

# Default collection name for the vault
DEFAULT_COLLECTION = "lexicon"


class QMDClient:
    """Wrapper around QMD CLI for hybrid search."""

    def __init__(
        self,
        collection: str = DEFAULT_COLLECTION,
        qmd_path: str | None = None,
    ):
        self.collection = collection
        self._qmd_path = qmd_path or shutil.which("qmd")
        if not self._qmd_path:
            logger.warning("QMD binary not found in PATH. Search will not work.")

    @property
    def available(self) -> bool:
        """Check if QMD is installed and accessible."""
        return self._qmd_path is not None

    async def _run(self, args: list[str], timeout: float = 30.0) -> str:
        """Run a QMD CLI command and return stdout."""
        if not self._qmd_path:
            raise RuntimeError("QMD binary not found. Install QMD first.")

        cmd = [self._qmd_path] + args
        logger.debug(f"Running: {' '.join(cmd)}")

        env = {**os.environ, "NO_COLOR": "1"}

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )

        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            raise TimeoutError(f"QMD command timed out after {timeout}s: {' '.join(cmd)}")

        if proc.returncode != 0:
            error = stderr.decode().strip()
            raise RuntimeError(f"QMD error (code {proc.returncode}): {error}")

        return stdout.decode().strip()

    async def query(
        self,
        text: str,
        n: int = 5,
        min_score: float = 0.0,
    ) -> list[dict[str, Any]]:
        """Hybrid search: BM25 + vector + auto-expansion + reranking.

        Uses `qmd query` which is the recommended search command.

        Args:
            text: Search query.
            n: Number of results to return.
            min_score: Minimum relevance score (0-1).

        Returns:
            List of {"path": "...", "score": float, "content": "..."}
        """
        args = [
            "query", text,
            "-n", str(n),
            "-c", self.collection,
            "--json",
        ]

        try:
            output = await self._run(args)
        except RuntimeError as e:
            logger.error(f"QMD query failed: {e}")
            return []

        if not output:
            return []

        try:
            results = json.loads(output)
        except json.JSONDecodeError:
            logger.error(f"QMD returned invalid JSON: {output[:200]}")
            return []

        # Handle both list and dict responses
        if isinstance(results, dict):
            results = results.get("results", [results])

        # Normalize results to our format
        normalized = []
        for r in results:
            score = r.get("score", 0.0)
            if score < min_score:
                continue
            normalized.append({
                "path": r.get("path", r.get("file", r.get("uri", ""))),
                "score": score,
                "content": r.get("content", r.get("text", r.get("snippet", ""))),
                "metadata": r.get("metadata", {}),
            })

        return normalized[:n]

    async def search_bm25(self, text: str, n: int = 10) -> list[dict[str, Any]]:
        """BM25-only keyword search (faster, no vector/rerank).

        Uses `qmd search` for pure keyword matching.

        Args:
            text: Search query.
            n: Number of results.

        Returns:
            List of {"path": "...", "score": float, "content": "..."}
        """
        args = [
            "search", text,
            "-n", str(n),
            "-c", self.collection,
            "--json",
        ]

        try:
            output = await self._run(args)
        except RuntimeError as e:
            logger.error(f"QMD BM25 search failed: {e}")
            return []

        if not output:
            return []

        try:
            results = json.loads(output)
        except json.JSONDecodeError:
            return []

        if isinstance(results, dict):
            results = results.get("results", [results])

        return [
            {
                "path": r.get("path", r.get("file", r.get("uri", ""))),
                "score": r.get("score", 0.0),
                "content": r.get("content", r.get("text", r.get("snippet", ""))),
            }
            for r in results[:n]
        ]

    async def get(self, doc_path: str) -> dict[str, Any] | None:
        """Get a specific document by path.

        Uses `qmd get <file>`.

        Args:
            doc_path: Path to the document.

        Returns:
            {"path": "...", "content": "..."} or None.
        """
        args = ["get", doc_path, "--json"]

        try:
            output = await self._run(args)
        except RuntimeError:
            return None

        if not output:
            return None

        try:
            return json.loads(output)
        except json.JSONDecodeError:
            # QMD get may return plain text, not JSON
            return {"path": doc_path, "content": output}

    async def update(self) -> bool:
        """Re-index all collections (picks up new/changed files).

        Uses `qmd update`.

        Returns:
            True if successful.
        """
        try:
            await self._run(["update"], timeout=120.0)
            return True
        except RuntimeError as e:
            logger.error(f"QMD update failed: {e}")
            return False

    async def embed(self) -> bool:
        """Generate/refresh vector embeddings.

        Uses `qmd embed`.

        Returns:
            True if successful.
        """
        try:
            await self._run(["embed"], timeout=120.0)
            return True
        except RuntimeError as e:
            logger.error(f"QMD embed failed: {e}")
            return False

    async def setup_collection(self, vault_path: Path | None = None) -> bool:
        """Set up the QMD collection pointing to the vault directory.

        Args:
            vault_path: Path to the Obsidian vault. Defaults to VAULT_DIR.

        Returns:
            True if successful.
        """
        vault = vault_path or VAULT_DIR

        args = [
            "collection", "add",
            str(vault),
            "--name", self.collection,
        ]

        try:
            await self._run(args)
            logger.info(f"QMD collection '{self.collection}' set up at {vault}")
            return True
        except RuntimeError as e:
            logger.error(f"QMD collection setup failed: {e}")
            return False
