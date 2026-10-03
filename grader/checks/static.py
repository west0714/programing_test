"""AST による静的チェック（「どう書いたか」）。"""

import ast

from .. import concepts
from . import CheckResult

# 実行前に止める import / 呼び出し（ファイル操作・プロセス生成・ネットワーク等）
DANGEROUS_MODULES = {
    "os", "sys", "subprocess", "shutil", "socket", "pathlib", "ctypes",
    "multiprocessing", "threading", "signal", "importlib", "builtins",
    "urllib", "http", "requests", "pickle", "tempfile", "glob", "io",
    "asyncio", "webbrowser", "ftplib", "smtplib", "sqlite3",
}
DANGEROUS_CALLS = {"open", "exec", "eval", "compile", "__import__", "breakpoint"}

# 実行結果が毎回変わり得る（出力一致を信用できない）
NONDETERMINISTIC_MODULES = {"random", "time", "datetime", "secrets", "uuid"}


def check_syntax(source):
    """構文解析。成功すれば (tree, result)、失敗すれば (None, result)。"""
    result = CheckResult("syntax")
    if not source.strip():
        return None, result.fail("EMPTY_FILE", "ファイルが空")
    try:
        return ast.parse(source), result
    except SyntaxError as e:
        return None, result.fail("SYNTAX_ERROR", f"SyntaxError: {e.msg}（{e.lineno}行目）")
    except ValueError as e:  # ヌル文字など
        return None, result.fail("SYNTAX_ERROR", f"解析不能: {e}")


def _imported_modules(tree):
    mods = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            mods.update(a.name.split(".")[0] for a in n.names)
        elif isinstance(n, ast.ImportFrom):
            mods.add((n.module or "").split(".")[0])
    return mods


def find_dangerous(tree):
    """実行してはいけない要素のリスト。空なら実行してよい。"""
    found = sorted(_imported_modules(tree) & DANGEROUS_MODULES)
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name):
            if n.func.id in DANGEROUS_CALLS:
                found.append(f"{n.func.id}()")
    return sorted(set(found))


def find_nondeterministic(tree):
    return sorted(_imported_modules(tree) & NONDETERMINISTIC_MODULES)


def check_requirements(tree, cfg):
    """課題固有の要件（require / nesting / variables / forbid）。"""
    result = CheckResult("requirements")
    for c in cfg.require:
        if not concepts.uses(tree, c):
            result.fail(f"MISSING:{c}", f"{c} が使われていない")
    for inner, outer in cfg.nesting:
        if not concepts.nested(tree, inner, outer):
            result.fail(
                f"NOT_NESTED:{inner}_in_{outer}", f"{outer} の中で {inner} が使われていない"
            )
    names = concepts.assigned_names(tree)
    for v in cfg.variables:
        if v not in names:
            result.fail(f"MISSING_VAR:{v}", f"変数 {v} への代入がない")
    for c in cfg.forbid:
        if concepts.uses(tree, c):
            result.fail(f"FORBIDDEN:{c}", f"禁止された {c} が使われている")
    return result


def find_unlearned(tree, allowed):
    """許可リスト外の要素（警告のみ・判定には使わない）。allowed が None なら判定しない。"""
    if allowed is None:
        return None
    return sorted(concepts.used_features(tree) - allowed)
