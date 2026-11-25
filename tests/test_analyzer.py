import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from lab6 import analyze
from lab6.analyzer import MAX_SOURCE_BYTES
from lab6.build import ROOT, build_native


class AnalyzerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        build_native()

    def values(self, source):
        result = analyze(source)
        self.assertTrue(result.success, "\n".join(map(str, result.diagnostics)))
        return {symbol.name: symbol.value for symbol in result.symbols}

    def assert_error(self, source, stage, fragment=None):
        result = analyze(source)
        self.assertFalse(result.success)
        errors = [error for error in result.diagnostics if error.stage == stage]
        self.assertTrue(errors, result.diagnostics)
        if fragment:
            self.assertTrue(any(fragment in error.message for error in errors), errors)
        return result

    def test_assignment_example(self):
        result = analyze("int a=1+2; bool x,z=TRUE;")
        self.assertTrue(result.success)
        self.assertEqual([(s.name, s.type, s.initialized, s.value) for s in result.symbols],
                         [("a", "int", True, 3), ("x", "bool", False, None), ("z", "bool", True, True)])

    def test_arithmetic_precedence(self):
        self.assertEqual(self.values("int a=2+3*4, b=(2+3)*4, c=20/5/2, d=8-3-1;"),
                         {"a": 14, "b": 20, "c": 2, "d": 4})

    def test_signed_division_and_remainder(self):
        self.assertEqual(self.values("int a=-7/3, b=-7%3, c=7/-3, d=7%-3;"),
                         {"a": -2, "b": -1, "c": -2, "d": 1})

    def test_unary_operators(self):
        self.assertEqual(self.values("int a=-(-3), b=2*-3, c=+4; bool d=!!TRUE;"),
                         {"a": 3, "b": -6, "c": 4, "d": True})

    def test_comparisons_and_boolean_precedence(self):
        result = self.values("bool a=TRUE||FALSE&&FALSE, b=1<2==TRUE, c=!(2>=3), d=3!=4, e=2<=2;")
        self.assertTrue(all(result.values()))

    def test_left_to_right_initialization(self):
        self.assertEqual(self.values("int a=2,b=a+1; int c=b*2; bool d=c==6;"),
                         {"a": 2, "b": 3, "c": 6, "d": True})

    def test_uninitialized_declarations_are_valid(self):
        self.assertEqual(self.values("int a,b; bool x,y;"), {"a": None, "b": None, "x": None, "y": None})

    def test_no_implicit_type_conversion(self):
        for source in ["int a=TRUE;", "bool a=1;", "int a=TRUE+1;", "bool a=TRUE==1;",
                       "bool a=1&&2;", "bool a=TRUE<FALSE;", "int a=-TRUE;", "bool a=!1;"]:
            with self.subTest(source=source):
                self.assert_error(source, "semantic")

    def test_short_circuit_evaluation(self):
        self.assertEqual(self.values("bool a=FALSE&&(1/0==0), b=TRUE||(1/0==0);"), {"a": False, "b": True})

    def test_skipped_branch_still_has_type_and_name_checks(self):
        self.assert_error("bool a=FALSE&&missing;", "semantic", "не объявлена")
        self.assert_error("bool a=TRUE||1;", "semantic", "требует")

    def test_duplicate_preserves_original_symbol(self):
        result = self.assert_error("int a=7; bool a=FALSE;", "semantic", "Повторное")
        self.assertEqual(len(result.symbols), 1)
        self.assertEqual(result.symbols[0].value, 7)

    def test_undefined_and_forward_references(self):
        self.assert_error("int a=b+1; int b=2;", "semantic", "не объявлена")

    def test_uninitialized_and_self_references(self):
        self.assert_error("int a; int b=a;", "semantic", "не инициализирована")
        self.assert_error("int a=a;", "semantic", "корректного значения")

    def test_failed_initializer_does_not_become_a_value(self):
        result = self.assert_error("int a=TRUE; int b=a; int c=5;", "semantic")
        self.assertEqual([s.state for s in result.symbols], ["invalid", "invalid", "initialized"])
        self.assertEqual(result.symbols[-1].value, 5)

    def test_division_and_remainder_by_zero(self):
        self.assert_error("int a=3/(2-2);", "semantic", "на ноль")
        self.assert_error("int a=3%0;", "semantic", "на ноль")

    def test_integer_boundaries(self):
        self.assertEqual(self.values("int a=-2147483648,b=2147483647,c=0003;"),
                         {"a": -(2**31), "b": 2**31 - 1, "c": 3})
        for source in ["int a=2147483648;", "int a=2147483647+1;", "int a=-2147483648/-1;",
                       "int a=--2147483648;", "int a=9999999999999999999999;"]:
            with self.subTest(source=source):
                self.assert_error(source, "semantic")

    def test_nonempty_program_required(self):
        for source in ("", "   ", "/* comment */"):
            with self.subTest(source=source):
                self.assert_error(source, "syntax")

    def test_invalid_syntax(self):
        for source in ["int a=1", "bool a=;", "int a=1,;", "int a=(1+2;", "float a=2;",
                       "int a=1; a=2;", "int a=1.5;", "int a=b=1;", "int;", "int a=1;;"]:
            with self.subTest(source=source):
                self.assertFalse(analyze(source).success)

    def test_invalid_identifiers(self):
        for source in ["int 1a=2;", "int a_b=2;", "int _a=2;", "int имя=2;"]:
            with self.subTest(source=source):
                self.assert_error(source, "lexical")

    def test_keywords_are_case_sensitive(self):
        self.assert_error("INT a=1;", "syntax")
        self.assert_error("bool a=true;", "semantic", "не объявлена")
        self.assertEqual(self.values("bool true=TRUE,a=true; int int1=1;"),
                         {"true": True, "a": True, "int1": 1})

    def test_comments_and_utf8(self):
        self.assertEqual(self.values("// Привет\nint a=1; /* 😀 */ bool b=TRUE;"), {"a": 1, "b": True})
        result = self.assert_error("int a=1; /*\n не закрыт", "lexical", "Unterminated")
        self.assertEqual((result.diagnostics[0].line, result.diagnostics[0].column), (1, 10))

    def test_token_positions(self):
        result = analyze("int a=1;\n  bool x,z=TRUE;")
        token = next(token for token in result.tokens if token.text == "z")
        self.assertEqual((token.kind, token.line, token.column), ("VAR", 2, 10))

    def test_utf8_error_columns(self):
        result = self.assert_error("/* Ж */ int a=@;", "lexical")
        lexical = next(error for error in result.diagnostics if error.stage == "lexical")
        self.assertEqual((lexical.line, lexical.column), (1, 15))
        result = self.assert_error("int a=😀;", "lexical")
        self.assertEqual(next(t.text for t in result.tokens if t.kind == "INVALID"), "😀")

    def test_end_of_file_error_position(self):
        result = self.assert_error("int a=1\n", "syntax")
        self.assertEqual((result.diagnostics[-1].line, result.diagnostics[-1].column), (2, 1))

    def test_recovery_reports_multiple_errors(self):
        result = self.assert_error("int a=;\nbool b=;\nint c=1;", "syntax")
        self.assertEqual(len([d for d in result.diagnostics if d.stage == "syntax"]), 2)
        self.assertEqual(result.symbols, [])
        self.assertIn("c", [t.text for t in result.tokens])

    def test_bom_and_line_endings(self):
        self.assertEqual(self.values("\ufeffint a=1;\r\nbool b=TRUE;\rint c=2;"),
                         {"a": 1, "b": True, "c": 2})

    def test_input_limits_and_nul(self):
        self.assert_error(" " * (MAX_SOURCE_BYTES + 1), "input")
        result = self.assert_error("int a=1;\n\0", "lexical")
        self.assertEqual((result.diagnostics[0].line, result.diagnostics[0].column), (2, 1))

    def test_deep_expression_without_python_recursion(self):
        expression = "+".join(["1"] * 1800)
        self.assertEqual(self.values(f"int a={expression};"), {"a": 1800})

    def test_all_example_files(self):
        for folder, valid in (("valid", True), ("invalid", False)):
            paths = sorted((ROOT / "examples" / folder).glob("*.mini"))
            self.assertTrue(paths)
            for path in paths:
                with self.subTest(path=path.name):
                    report = analyze(path.read_text(encoding="utf-8"))
                    self.assertEqual(report.success, valid, report.diagnostics)

    def test_json_and_tree_exports(self):
        report = analyze("int a=1+2;")
        data = json.loads(report.to_json())
        self.assertTrue(data["success"])
        self.assertEqual(data["backend"], "GNU Bison + Flex")
        self.assertIn("Binary: +", report.tree_text())
        self.assertIn('digraph AST', report.to_dot())
        self.assertIn('->', report.to_dot())


class CLITests(unittest.TestCase):
    def cli(self, *arguments, input=None, cwd=ROOT):
        return subprocess.run(
            [sys.executable, "-X", "utf8", str(ROOT / "main.py"), *arguments],
            input=input, cwd=cwd, capture_output=True, text=True, encoding="utf-8", timeout=30,
        )

    def test_valid_json_output(self):
        result = self.cli("--code", "int a=1+2; bool x,z=TRUE;", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["symbols"][0]["value"], 3)

    def test_utf8_output_with_legacy_windows_encoding(self):
        environment = os.environ.copy()
        environment["PYTHONIOENCODING"] = "cp1251"
        result = subprocess.run([sys.executable, str(ROOT / "main.py"), "--code", "int a=1;"],
                                env=environment, capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Таблица переменных", result.stdout.decode("utf-8"))

    def test_invalid_program_exit_code(self):
        result = self.cli("--code", "int a=TRUE;", "--json")
        self.assertEqual(result.returncode, 1)
        self.assertFalse(json.loads(result.stdout)["success"])

    def test_missing_file_exit_code(self):
        result = self.cli("missing-file.mini")
        self.assertEqual(result.returncode, 2)
        self.assertIn("Ошибка запуска", result.stderr)

    def test_no_arguments_shows_usage(self):
        result = self.cli()
        self.assertEqual(result.returncode, 2)
        self.assertIn("--code", result.stdout)

    def test_stdin(self):
        result = self.cli("-", "--json", input="int a=42;")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["symbols"][0]["value"], 42)

    def test_file_from_another_working_directory(self):
        with tempfile.TemporaryDirectory(prefix="lab6 ") as directory:
            source = Path(directory) / "пример.mini"
            source.write_text("int a=2;", encoding="utf-8-sig")
            result = self.cli(str(source), "--tokens", "--tree", cwd=directory)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("OK", result.stdout)
            self.assertIn("Токены Flex", result.stdout)

    def test_report_file_exports(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "report.json"
            dot = Path(directory) / "tree.dot"
            result = self.cli("--code", "bool a=TRUE;", "--output", str(output), "--dot", str(dot))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(json.loads(output.read_text(encoding="utf-8"))["success"])
            self.assertIn("digraph AST", dot.read_text(encoding="utf-8"))

    def test_export_cannot_overwrite_source(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "input.mini"
            source.write_text("int a=2;", encoding="utf-8")
            result = self.cli(str(source), "--output", str(source))
            self.assertEqual(result.returncode, 2)
            self.assertEqual(source.read_text(encoding="utf-8"), "int a=2;")


if __name__ == "__main__":
    unittest.main()
