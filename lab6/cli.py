from __future__ import annotations

import argparse
from pathlib import Path
import sys

from .analyzer import analyze
from .build import BuildError, build_native
from .model import Analysis, format_value


def print_table(headers: tuple[str, ...], rows: list[tuple[str, ...]]) -> None:
    widths = [max(len(header), *(len(row[i]) for row in rows)) for i, header in enumerate(headers)]
    template = "  ".join(f"{{:<{width}}}" for width in widths)
    print(template.format(*headers))
    print(template.format(*("─" * width for width in widths)))
    for row in rows:
        print(template.format(*row))


def print_report(report: Analysis, *, tokens: bool, tree: bool) -> None:
    print("BISON + FLEX — анализатор объявлений int / bool")
    if report.success:
        print("Результат: OK — программа корректна.")
    else:
        print(f"Результат: ERROR — ошибок: {len(report.diagnostics)}.")
        for diagnostic in report.diagnostics:
            print(f"  {diagnostic}")
    if report.symbols:
        print("\nТаблица переменных:")
        print_table(("VAR", "Тип", "Значение", "Позиция"), [
            (symbol.name, symbol.type,
             "ошибка инициализации" if symbol.state == "invalid" else format_value(symbol.value),
             f"{symbol.line}:{symbol.column}")
            for symbol in report.symbols
        ])
    if tokens:
        print("\nТокены Flex:")
        if report.tokens:
            print_table(("Токен", "Лексема", "Строка", "Столбец"), [
                (token.kind, token.text, str(token.line), str(token.column)) for token in report.tokens
            ])
        else:
            print("Нет токенов.")
    if tree:
        print("\nАбстрактное синтаксическое дерево Bison:")
        print(report.tree_text())


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(
        description="Лабораторная № 6. Анализатор BISON+FLEX: объявления VAR типа int и bool.",
        epilog='Пример: python main.py --code "int a=1+2; bool x,z=TRUE;"',
    )
    parser.add_argument("file", nargs="?", help="файл UTF-8 с программой; '-' — читать stdin")
    parser.add_argument("--code", help="программа прямо в аргументе командной строки")
    parser.add_argument("--tokens", action="store_true", help="вывести таблицу токенов Flex")
    parser.add_argument("--tree", action="store_true", help="вывести абстрактное дерево Bison")
    parser.add_argument("--json", action="store_true", help="вывести результат в формате JSON")
    parser.add_argument("--output", type=Path, help="сохранить JSON-отчёт в файл")
    parser.add_argument("--dot", type=Path, help="сохранить дерево в формате Graphviz DOT")
    parser.add_argument("--build", action="store_true", help="принудительно пересобрать Flex/Bison")
    args = parser.parse_args(argv)
    if args.file is not None and args.code is not None:
        parser.error("укажите либо файл, либо --code")
    if args.file is None and args.code is None and not args.build:
        parser.print_help()
        return 2
    if args.file is None and args.code is None and any((args.json, args.output, args.dot, args.tokens, args.tree)):
        parser.error("для отчёта нужна программа: файл или --code")
    try:
        if args.build:
            binary = build_native(force=True)
            if args.file is None and args.code is None:
                print(f"Анализатор собран: {binary}")
                return 0
        if args.code is not None:
            source = args.code
        elif args.file == "-":
            source = sys.stdin.buffer.read().decode("utf-8-sig")
        else:
            source = Path(args.file).read_text(encoding="utf-8-sig")
        destinations = [path.resolve() for path in (args.output, args.dot) if path is not None]
        if args.file not in (None, "-") and Path(args.file).resolve() in destinations:
            parser.error("файл отчёта должен отличаться от исходной программы")
        if len(set(destinations)) != len(destinations):
            parser.error("для JSON и DOT нужны разные файлы")
        report = analyze(source)
        if args.output:
            args.output.write_text(report.to_json() + "\n", encoding="utf-8")
        if args.dot:
            args.dot.write_text(report.to_dot(), encoding="utf-8")
        if args.json:
            print(report.to_json())
        else:
            print_report(report, tokens=args.tokens, tree=args.tree)
        return 0 if report.success else 1
    except (BuildError, OSError, UnicodeError) as error:
        print(f"Ошибка запуска: {error}", file=sys.stderr)
        return 2
