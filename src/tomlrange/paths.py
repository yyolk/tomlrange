from __future__ import annotations

from typing import Literal

Overlap = Literal["reject", "allow", "merge"]


def join_path(parent: str, child: str) -> str:
    if parent in {"", "."}:
        return child
    return f"{parent}.{child}"


def index_path(parent: str, i: int) -> str:
    if parent in {"", "."}:
        return f"[{i}]"
    return f"{parent}[{i}]"
