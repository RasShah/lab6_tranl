from __future__ import annotations

import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import threading

ROOT = Path(__file__).resolve().parent.parent
BUILD_DIR = ROOT / "build"
EXECUTABLE = BUILD_DIR / ("analyzer_native.exe" if os.name == "nt" else "analyzer_native")
SOURCES = (
    "files/mini.l", "files/mini.y", "native/ast.h", "native/ast.c",
    "native/main.c", "lab6/build.py",
)
_BUILD_LOCK = threading.Lock()
SUBPROCESS_OPTIONS = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}


class BuildError(RuntimeError):
    pass


def _tool(variable: str, names: tuple[str, ...]) -> str:
    configured = os.environ.get(variable)
    if configured:
        found = shutil.which(configured)
        if found:
            return found
        raise BuildError(f"{variable} указывает на недоступную программу: {configured}")
    for name in names:
        found = shutil.which(name)
        if found:
            return found
    if os.name == "nt":
        roots = [Path(os.environ.get("MSYS2_ROOT", "C:/msys64"))]
        for root in roots:
            for folder in ("ucrt64/bin", "mingw64/bin", "usr/bin"):
                for name in names:
                    candidate = root / folder / f"{name}.exe"
                    if candidate.is_file():
                        return str(candidate)
    raise BuildError(
        f"Не найден {names[0]}. Установите GNU Bison, Flex и GCC; "
        f"см. README.md. Путь можно задать переменной {variable}."
    )


def _fingerprint() -> str:
    digest = hashlib.sha256()
    for source in SOURCES:
        digest.update((ROOT / source).read_bytes())
    for key in ("BISON", "FLEX", "CC", "MSYS2_ROOT"):
        digest.update(os.environ.get(key, "").encode())
    return digest.hexdigest()


def build_native(*, force: bool = False) -> Path:
    with _BUILD_LOCK:
        fingerprint = _fingerprint()
        stamp = BUILD_DIR / "source.sha256"
        if not force and EXECUTABLE.is_file() and stamp.is_file():
            if stamp.read_text(encoding="ascii").strip() == fingerprint:
                return EXECUTABLE

        bison = _tool("BISON", ("bison", "win_bison"))
        flex = _tool("FLEX", ("flex", "win_flex"))
        compiler = _tool("CC", ("gcc", "clang", "cc"))
        environment = os.environ.copy()
        environment["PATH"] = os.pathsep.join(
            [str(Path(tool).parent) for tool in (bison, flex, compiler)]
            + [environment.get("PATH", "")]
        )
        environment["LC_ALL"] = "C"
        BUILD_DIR.mkdir(exist_ok=True)
        pending = BUILD_DIR / ("analyzer_pending.exe" if os.name == "nt" else "analyzer_pending")
        commands = [
            [bison, "--warnings=all,error", "--defines=build/parser.h",
             "--output=build/parser.c", "--report=state", "--report-file=build/parser.output",
             "files/mini.y"],
            [flex, "--outfile=build/lexer.c", "files/mini.l"],
            [compiler, "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
             "-Inative", "-Ibuild", "build/parser.c", "build/lexer.c",
             "native/ast.c", "native/main.c", "-o", str(pending)],
        ]
        if Path(flex).stem.lower() == "win_flex":
            commands[1].insert(1, "--wincompat")
        for command in commands:
            try:
                completed = subprocess.run(
                    command, cwd=ROOT, env=environment, capture_output=True,
                    timeout=90, **SUBPROCESS_OPTIONS,
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                raise BuildError(f"Не удалось запустить {Path(command[0]).name}: {exc}") from exc
            if completed.returncode:
                details = (completed.stderr + completed.stdout).decode("utf-8", errors="replace")
                raise BuildError(f"Ошибка сборки ({Path(command[0]).name}):\n{details}")
        pending.replace(EXECUTABLE)
        stamp.write_text(fingerprint + "\n", encoding="ascii")
        return EXECUTABLE


if __name__ == "__main__":
    try:
        print(build_native(force=True))
    except (BuildError, OSError) as error:
        raise SystemExit(str(error)) from error
