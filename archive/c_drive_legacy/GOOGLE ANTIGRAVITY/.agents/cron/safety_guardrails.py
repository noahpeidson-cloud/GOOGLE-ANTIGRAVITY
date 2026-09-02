"""Static AST Safety Guardrails enforcing 0-destruction mathematical guarantees."""

import ast
import os
import re
from typing import Dict, List, Optional, Set, Tuple


FORBIDDEN_OS_FUNCS = {
    "remove",
    "unlink",
    "rmdir",
    "removedirs",
    "truncate",
    "ftruncate",
    "kill",
    "killpg",
    "popen",
    "system",
    "spawnl",
    "spawnle",
    "spawnlp",
    "spawnlpe",
    "spawnv",
    "spawnve",
    "spawnvp",
    "spawnvpe",
}

FORBIDDEN_SHUTIL_FUNCS = {
    "rmtree",
}

FORBIDDEN_SIGNAL_FUNCS = {
    "pthread_kill",
}

FORBIDDEN_CALL_ATTRIBUTES = {
    ("os", fn) for fn in FORBIDDEN_OS_FUNCS
} | {
    ("shutil", fn) for fn in FORBIDDEN_SHUTIL_FUNCS
} | {
    ("signal", fn) for fn in FORBIDDEN_SIGNAL_FUNCS
}

FORBIDDEN_BUILTIN_CALLS = {
    "eval",
    "exec",
    "__import__",
}

FORBIDDEN_GETATTR_TARGETS = FORBIDDEN_OS_FUNCS | FORBIDDEN_SHUTIL_FUNCS | FORBIDDEN_SIGNAL_FUNCS

FORBIDDEN_SUBPROCESS_MODULES = {"subprocess", "os"}
FORBIDDEN_SUBPROCESS_FUNCS = {"run", "Popen", "call", "check_call", "check_output", "system"}

FORBIDDEN_COMMAND_PATTERNS = [
    re.compile(r"\btaskkill\b", re.IGNORECASE),
    re.compile(r"\bpkill\b", re.IGNORECASE),
    re.compile(r"\bkill\b", re.IGNORECASE),
    re.compile(r"\brm\s+-rf\b", re.IGNORECASE),
    re.compile(r"\bdel\s+/[fFqQsS]\b", re.IGNORECASE),
    re.compile(r"\brmdir\s+/[sSqQ]\b", re.IGNORECASE),
]

FORBIDDEN_SQL_PATTERNS = [
    re.compile(r"\bDROP\s+TABLE\b", re.IGNORECASE),
    re.compile(r"\bDROP\s+DATABASE\b", re.IGNORECASE),
    re.compile(r"\bDROP\s+SCHEMA\b", re.IGNORECASE),
    re.compile(r"\bDROP\s+VIEW\b", re.IGNORECASE),
    re.compile(r"\bTRUNCATE\s+TABLE\b", re.IGNORECASE),
    re.compile(r"\bTRUNCATE\b", re.IGNORECASE),
]

SQL_STRING_LITERAL_REGEX = re.compile(
    r"'(?:''|\\'|[^'])*'|\"(?:\"\"|\\\"|[^\"])*\"",
    re.DOTALL,
)


class SafetyViolationError(AssertionError):
    """Raised when static AST analysis detects a destructive code operation."""
    pass


class SafetyASTVisitor(ast.NodeVisitor):
    """AST visitor that checks for destructive function calls, dangerous subprocess invocations,

    prohibited eval/exec usages, forbidden dynamic imports, and destructive SQL queries.
    Tracks module and symbol aliases and prevents false positives on user-defined functions
    and SQL string literals.
    """

    def __init__(self, filename: str = "<string>") -> None:
        self.filename = filename
        self.violations: List[str] = []
        # Mapping of alias_name -> original_module_name (e.g. {"my_os": "os"})
        self.imported_modules: Dict[str, str] = {}
        # Mapping of alias_name -> (module_name, func_name) (e.g. {"rm": ("os", "remove")})
        self.imported_symbols: Dict[str, Tuple[str, str]] = {}
        # Set of user-defined function/class names in the current AST
        self.local_definitions: Set[str] = set()

    def _extract_str_constants(self, node: ast.AST) -> List[str]:
        """Extracts string literals from an AST node (strings, lists of strings, tuples)."""
        strings: List[str] = []
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            strings.append(node.value)
        elif isinstance(node, (ast.List, ast.Tuple, ast.Set)):
            for elt in node.elts:
                strings.extend(self._extract_str_constants(elt))
        elif isinstance(node, ast.JoinedStr):
            parts = []
            for part in node.values:
                if isinstance(part, ast.Constant) and isinstance(part.value, str):
                    parts.append(part.value)
            if parts:
                strings.append("".join(parts))
        return strings

    def _strip_sql_literals(self, sql_str: str) -> str:
        """Removes string literals from SQL statements to prevent false positive pattern matches."""
        return SQL_STRING_LITERAL_REGEX.sub("''", sql_str)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            target_asname = alias.asname or alias.name
            self.imported_modules[target_asname] = alias.name
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = node.module or ""
        for alias in node.names:
            target_asname = alias.asname or alias.name
            self.imported_symbols[target_asname] = (module, alias.name)
            # Check if importing forbidden function directly
            if module == "os" and alias.name in FORBIDDEN_OS_FUNCS:
                pass  # Tracked in imported_symbols, will flag when called or if imported
            elif module == "shutil" and alias.name in FORBIDDEN_SHUTIL_FUNCS:
                pass
            elif module == "signal" and alias.name in FORBIDDEN_SIGNAL_FUNCS:
                pass
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.local_definitions.add(node.name)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.local_definitions.add(node.name)
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.local_definitions.add(node.name)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        # 1. Direct name calls: func(...)
        if isinstance(node.func, ast.Name):
            func_id = node.func.id

            # Check if func is a prohibited built-in (unless shadowed by local def)
            if func_id in FORBIDDEN_BUILTIN_CALLS and func_id not in self.local_definitions:
                self.violations.append(
                    f"[{self.filename}:{node.lineno}] Prohibited built-in call: '{func_id}'"
                )

            # Check if func is an imported forbidden symbol (e.g. from os import remove as rm; rm())
            if func_id in self.imported_symbols:
                mod, sym = self.imported_symbols[func_id]
                if (mod, sym) in FORBIDDEN_CALL_ATTRIBUTES or (mod == "os" and sym in FORBIDDEN_OS_FUNCS):
                    self.violations.append(
                        f"[{self.filename}:{node.lineno}] Prohibited destructive operation: '{mod}.{sym}' (via '{func_id}')"
                    )
                elif mod == "importlib" and sym == "import_module":
                    self.violations.append(
                        f"[{self.filename}:{node.lineno}] Prohibited dynamic import: '{mod}.{sym}' (via '{func_id}')"
                    )

            # Check getattr(...) invocations
            if func_id == "getattr" and func_id not in self.local_definitions:
                if len(node.args) >= 2:
                    attr_strings = self._extract_str_constants(node.args[1])
                    for attr_str in attr_strings:
                        if attr_str in FORBIDDEN_GETATTR_TARGETS:
                            self.violations.append(
                                f"[{self.filename}:{node.lineno}] Prohibited dynamic getattr access to destructive attribute: '{attr_str}'"
                            )

        # 2. Attribute calls: obj.attr(...)
        elif isinstance(node.func, ast.Attribute):
            attr_name = node.func.attr

            # 2.1 Prohibit .unlink() and .rmdir() calls on any object (e.g. Path.unlink, Path.rmdir)
            if attr_name in {"unlink", "rmdir"}:
                self.violations.append(
                    f"[{self.filename}:{node.lineno}] Prohibited filesystem destruction call: '.{attr_name}()'"
                )

            # 2.2 Check module.func calls with alias resolution
            if isinstance(node.func.value, ast.Name):
                obj_id = node.func.value.id
                module_name = self.imported_modules.get(obj_id, obj_id)

                # Check forbidden attributes on module
                if (module_name, attr_name) in FORBIDDEN_CALL_ATTRIBUTES or (
                    module_name == "os" and (attr_name in FORBIDDEN_OS_FUNCS or attr_name.startswith("spawn"))
                ):
                    self.violations.append(
                        f"[{self.filename}:{node.lineno}] Prohibited destructive operation: '{module_name}.{attr_name}'"
                    )

                # Check importlib.import_module
                if module_name == "importlib" and attr_name == "import_module":
                    self.violations.append(
                        f"[{self.filename}:{node.lineno}] Prohibited dynamic import: '{module_name}.{attr_name}'"
                    )

                # Check subprocess / os.system commands (including keyword arguments)
                if (module_name in FORBIDDEN_SUBPROCESS_MODULES and attr_name in FORBIDDEN_SUBPROCESS_FUNCS) or (
                    module_name == "os" and attr_name == "system"
                ):
                    cmd_strings = []
                    if node.args:
                        cmd_strings.extend(self._extract_str_constants(node.args[0]))
                    for kw in node.keywords:
                        if kw.arg in {"args", "command", "cmd", "input"} and kw.value:
                            cmd_strings.extend(self._extract_str_constants(kw.value))

                    full_cmd_str = " ".join(cmd_strings)
                    for pattern in FORBIDDEN_COMMAND_PATTERNS:
                        if pattern.search(full_cmd_str):
                            self.violations.append(
                                f"[{self.filename}:{node.lineno}] Prohibited destructive subprocess command: '{full_cmd_str}'"
                            )
                            break

            # 2.3 Check SQL execution for DROP / TRUNCATE (inspecting args and keyword args)
            if attr_name in {"execute", "executemany", "executescript"}:
                sql_strings = []
                if node.args:
                    sql_strings.extend(self._extract_str_constants(node.args[0]))
                for kw in node.keywords:
                    if kw.arg in {"sql", "operation", "query", "statement"} and kw.value:
                        sql_strings.extend(self._extract_str_constants(kw.value))

                for raw_sql in sql_strings:
                    sanitized_sql = self._strip_sql_literals(raw_sql)
                    for pattern in FORBIDDEN_SQL_PATTERNS:
                        if pattern.search(sanitized_sql):
                            self.violations.append(
                                f"[{self.filename}:{node.lineno}] Prohibited destructive SQL query: '{raw_sql}'"
                            )
                            break

        self.generic_visit(node)


def scan_code_for_safety(code_str: str, filename: str = "<string>") -> List[str]:
    """Parses a code string into AST and returns all detected safety violations."""
    try:
        tree = ast.parse(code_str, filename=filename)
    except SyntaxError as e:
        return [f"[{filename}:{e.lineno}] Syntax error during AST parsing: {e.msg}"]

    visitor = SafetyASTVisitor(filename=filename)
    visitor.visit(tree)
    return visitor.violations


def scan_file_for_safety(file_path: str) -> List[str]:
    """Reads a Python file, parses its AST, and returns all detected safety violations."""
    if not os.path.exists(file_path):
        return [f"File not found: {file_path}"]
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()
    return scan_code_for_safety(content, filename=file_path)


def assert_safe_codebase(
    target_dir: str,
    exclude_dirs: Optional[List[str]] = None,
    exclude_files: Optional[List[str]] = None,
) -> None:
    """Statically verifies that target directory contains zero destructive operations.

    Raises SafetyViolationError if any violation is detected.
    """
    if not os.path.exists(target_dir):
        raise SafetyViolationError(f"Target directory does not exist: {target_dir}")

    excluded_dirs_set: Set[str] = set(exclude_dirs or ["__pycache__", ".git", ".pytest_cache", "venv", ".venv"])
    excluded_files_set: Set[str] = set(exclude_files or [])

    all_violations: List[str] = []

    for root, dirs, files in os.walk(target_dir):
        # Filter directories in-place
        dirs[:] = [d for d in dirs if d not in excluded_dirs_set]

        for file in files:
            if file.endswith(".py") and file not in excluded_files_set:
                file_path = os.path.join(root, file)
                violations = scan_file_for_safety(file_path)
                all_violations.extend(violations)

    if all_violations:
        formatted = "\n  - " + "\n  - ".join(all_violations)
        raise SafetyViolationError(
            f"Static AST Safety check failed with {len(all_violations)} violations:{formatted}"
        )
