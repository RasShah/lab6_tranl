from __future__ import annotations

from .model import Analysis, Diagnostic, Node, Symbol

INT_MIN = -(2**31)
INT_MAX = 2**31 - 1


class SemanticFailure(Exception):
    def __init__(self, node: Node, message: str):
        self.diagnostic = Diagnostic("semantic", message, node.line, node.column)
        super().__init__(message)


class SemanticAnalyzer:
    def __init__(self, report: Analysis):
        self.report = report
        self.nodes = report.nodes
        self.symbols: dict[str, Symbol] = {}

    def run(self) -> None:
        if self.report.root is None:
            return
        for declaration_id in self.nodes[self.report.root].children:
            declaration = self.nodes[declaration_id]
            variables = self.nodes[declaration.children[0]]
            for variable_id in variables.children:
                variable = self.nodes[variable_id]
                try:
                    self._declare(variable, declaration.value)
                except SemanticFailure as error:
                    self.report.diagnostics.append(error.diagnostic)
        self.report.symbols = list(self.symbols.values())

    def _declare(self, node: Node, declared_type: str) -> None:
        if node.value in self.symbols:
            first = self.symbols[node.value]
            raise SemanticFailure(node, f"Повторное объявление '{node.value}'; первое — {first.line}:{first.column}.")
        symbol = Symbol(node.value, declared_type, node.line, node.column)
        self.symbols[node.value] = symbol
        if not node.children:
            return
        symbol.state = "invalid"
        expression = self.nodes[node.children[0]]
        actual_type = self._infer(expression)
        if actual_type != declared_type:
            raise SemanticFailure(expression, f"Нельзя инициализировать {declared_type} '{node.value}' выражением типа {actual_type}.")
        symbol.value = self._evaluate(expression)
        symbol.initialized = True
        symbol.state = "initialized"

    def _infer(self, root: Node) -> str:
        types: dict[int, str] = {}
        pending = [(root.id, False)]
        while pending:
            node_id, visited = pending.pop()
            node = self.nodes[node_id]
            if not visited:
                pending.append((node_id, True))
                pending.extend((child, False) for child in reversed(node.children))
                continue
            if node.kind in ("Integer", "Boolean"):
                types[node_id] = "int" if node.kind == "Integer" else "bool"
            elif node.kind == "Identifier":
                symbol = self.symbols.get(node.value)
                if symbol is None:
                    raise SemanticFailure(node, f"Переменная '{node.value}' не объявлена.")
                if not symbol.initialized:
                    reason = "не имеет корректного значения" if symbol.state == "invalid" else "не инициализирована"
                    raise SemanticFailure(node, f"Переменная '{node.value}' {reason}.")
                types[node_id] = symbol.type
            elif node.kind == "Group":
                types[node_id] = types[node.children[0]]
            elif node.kind == "Unary":
                required = "bool" if node.value == "!" else "int"
                actual = types[node.children[0]]
                if actual != required:
                    raise SemanticFailure(node, f"Оператор '{node.value}' требует {required}, получен {actual}.")
                types[node_id] = required
            elif node.kind == "Binary":
                left, right = (types[child] for child in node.children)
                op = node.value
                if op in ("==", "!="):
                    if left != right:
                        raise SemanticFailure(node, f"Оператор '{op}' требует одинаковые типы, получены {left} и {right}.")
                    result_type = "bool"
                else:
                    required = "bool" if op in ("&&", "||") else "int"
                    if left != required or right != required:
                        raise SemanticFailure(node, f"Оператор '{op}' требует два {required}, получены {left} и {right}.")
                    result_type = "bool" if op in ("&&", "||", "<", ">", "<=", ">=") else "int"
                types[node_id] = result_type
        return types[root.id]

    @staticmethod
    def _bounded(value: int | bool, node: Node) -> int | bool:
        if type(value) is int and not INT_MIN <= value <= INT_MAX:
            raise SemanticFailure(node, "Переполнение int: допустим диапазон от -2147483648 до 2147483647.")
        return value

    def _evaluate(self, root: Node) -> int | bool:
        values: dict[int, int | bool] = {}
        pending = [(root.id, 0)]
        while pending:
            node_id, phase = pending.pop()
            node = self.nodes[node_id]
            if node.kind == "Integer":
                digits = node.value.lstrip("0") or "0"
                if len(digits) > 10:
                    raise SemanticFailure(node, "Целочисленный литерал выходит за диапазон int.")
                values[node_id] = self._bounded(int(digits), node)
            elif node.kind == "Boolean":
                values[node_id] = node.value == "TRUE"
            elif node.kind == "Identifier":
                values[node_id] = self.symbols[node.value].value
            elif node.kind in ("Unary", "Group"):
                child = self.nodes[node.children[0]]
                if node.kind == "Unary" and node.value == "-" and child.kind == "Integer" and child.value.lstrip("0") == "2147483648":
                    values[node_id] = INT_MIN
                    continue
                if phase == 0:
                    pending.extend([(node_id, 1), (child.id, 0)])
                    continue
                value = values[child.id]
                if node.kind == "Unary":
                    value = not value if node.value == "!" else (-value if node.value == "-" else +value)
                values[node_id] = self._bounded(value, node)
            else:
                left_id, right_id = node.children
                if phase == 0:
                    pending.extend([(node_id, 1), (left_id, 0)])
                    continue
                left = values[left_id]
                if phase == 1:
                    if (node.value == "&&" and not left) or (node.value == "||" and left):
                        values[node_id] = bool(left)
                        continue
                    pending.extend([(node_id, 2), (right_id, 0)])
                    continue
                right = values[right_id]
                values[node_id] = self._bounded(self._binary(node, left, right), node)
        return values[root.id]

    @staticmethod
    def _binary(node: Node, left: int | bool, right: int | bool) -> int | bool:
        op = node.value
        if op in ("/", "%"):
            if right == 0:
                raise SemanticFailure(node, "Деление на ноль." if op == "/" else "Остаток от деления на ноль.")
            quotient = (abs(left) // abs(right)) * (-1 if (left < 0) != (right < 0) else 1)
            return quotient if op == "/" else left - quotient * right
        if op == "+": return left + right
        if op == "-": return left - right
        if op == "*": return left * right
        if op == "<": return left < right
        if op == ">": return left > right
        if op == "<=": return left <= right
        if op == ">=": return left >= right
        if op == "==": return left == right
        if op == "!=": return left != right
        if op == "&&": return bool(left and right)
        if op == "||": return bool(left or right)
        raise ValueError(f"Unknown operator: {op}")
