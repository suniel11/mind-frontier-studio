from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any


@dataclass
class RenderNode:
    name: str
    status: str
    output: str = ""
    detail: str = ""

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


class RenderGraph:
    def __init__(self, project_dir: Path):
        self.project_dir = project_dir
        self.nodes: list[RenderNode] = []

    def mark(self, name: str, status: str, output: str = "", detail: str = "") -> None:
        self.nodes.append(RenderNode(name=name, status=status, output=output, detail=detail))
        self.save()

    def save(self) -> Path:
        path = self.project_dir / "render-graph.json"
        payload = {"nodes": [node.model_dump() for node in self.nodes]}
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return path
