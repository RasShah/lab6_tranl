from __future__ import annotations

import json
import subprocess

from .build import BuildError, SUBPROCESS_OPTIONS, build_native
from .model import Analysis, Diagnostic, Node, Token
from .semantics import SemanticAnalyzer

MAX_SOURCE_BYTES = 256 * 1024


def analyze(source: str) -> Analysis:
    source = source.removeprefix("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
    payload = source.encode("utf-8")
    if len(payload) > MAX_SOURCE_BYTES:
        return Analysis(diagnostics=[Diagnostic("input", "Размер программы превышает 256 КиБ.", 1, 1)])
    if "\0" in source:
        offset = source.index("\0")
        return Analysis(diagnostics=[Diagnostic("lexical", "Недопустимый нулевой символ.",
                                               source.count("\n", 0, offset) + 1,
                                               offset - source.rfind("\n", 0, offset))])
    engine = build_native()
    try:
        process = subprocess.run([str(engine)], input=payload, capture_output=True,
                                 timeout=15, **SUBPROCESS_OPTIONS)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise BuildError(f"Не удалось выполнить анализ: {error}") from error
    if process.returncode not in (0, 1):
        detail = process.stderr.decode("utf-8", errors="replace")
        raise BuildError(f"Анализатор завершился с кодом {process.returncode}: {detail}")
    try:
        data = json.loads(process.stdout.decode("utf-8"))
    except (ValueError, UnicodeError) as error:
        raise BuildError("Нативный анализатор вернул некорректный JSON.") from error
    report = Analysis(
        backend=data["backend"], root=data["root"],
        nodes=[Node(**node) for node in data["nodes"]],
        tokens=[Token(**token) for token in data["tokens"]],
        diagnostics=[Diagnostic(**item) for item in data["diagnostics"]],
    )
    if not report.diagnostics:
        SemanticAnalyzer(report).run()
    return report
