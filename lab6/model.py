from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json


@dataclass
class Token:
    kind: str
    text: str
    line: int
    column: int


@dataclass
class Node:
    id: int
    kind: str
    value: str
    line: int
    column: int
    children: list[int]

    @property
    def label(self) -> str:
        return f"{self.kind}: {self.value}" if self.value else self.kind


@dataclass
class Diagnostic:
    stage: str
    message: str
    line: int
    column: int

    def __str__(self) -> str:
        stage = {"lexical": "Лексическая", "syntax": "Синтаксическая",
                 "semantic": "Семантическая", "input": "Входная"}.get(self.stage, self.stage)
        return f"{self.line}:{self.column}: {stage} ошибка: {self.message}"


@dataclass
class Symbol:
    name: str
    type: str
    line: int
    column: int
    initialized: bool = False
    value: int | bool | None = None
    state: str = "uninitialized"


def format_value(value: int | bool | None) -> str:
    if value is None:
        return "не инициализирована"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    return str(value)


@dataclass
class Analysis:
    backend: str = "GNU Bison + Flex"
    root: int | None = None
    nodes: list[Node] = field(default_factory=list)
    tokens: list[Token] = field(default_factory=list)
    diagnostics: list[Diagnostic] = field(default_factory=list)
    symbols: list[Symbol] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return not self.diagnostics

    def to_dict(self) -> dict:
        return {"success": self.success, **asdict(self)}

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    def tree_text(self) -> str:
        if self.root is None:
            return "Дерево не построено."
        lines = []
        pending = [(self.root, 0)]
        while pending:
            node_id, depth = pending.pop()
            node = self.nodes[node_id]
            prefix = "  " * min(depth, 40) + (f"[{depth}] " if depth > 40 else "")
            lines.append(f"{prefix}{node.label}  ({node.line}:{node.column})")
            pending.extend((child, depth + 1) for child in reversed(node.children))
        return "\n".join(lines)

    def to_dot(self) -> str:
        lines = ['digraph AST {', '  graph [ordering="out"];',
                 '  node [shape=box, fontname="Consolas"];']
        pending = [self.root] if self.root is not None else []
        while pending:
            node = self.nodes[pending.pop()]
            label = json.dumps(node.label, ensure_ascii=False)
            lines.append(f"  n{node.id} [label={label}];")
            for child in node.children:
                lines.append(f"  n{node.id} -> n{child};")
            pending.extend(reversed(node.children))
        lines.append('}')
        return "\n".join(lines) + "\n"
