"""学習要素（概念）テーブル。

授業で新しい要素が登場したら CONCEPTS に1行追加する。
各値は「ASTノードを受け取り、その概念に該当するかを返す述語」。
"""

import ast
import builtins


def node(*types):
    return lambda n: isinstance(n, types)


def call_of(name):
    """組込み関数などの名前呼び出し: name(...)"""
    return lambda n: (
        isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == name
    )


def method_of(name):
    """メソッド呼び出し: x.name(...)"""
    return lambda n: (
        isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr == name
    )


def binop(op):
    """二項演算（累算代入 += なども含む）"""
    return lambda n: isinstance(n, (ast.BinOp, ast.AugAssign)) and isinstance(n.op, op)


def any_of(*preds):
    return lambda n: any(p(n) for p in preds)


CONCEPTS = {
    # 入出力・型変換
    "print": call_of("print"),
    "input": call_of("input"),
    "int": call_of("int"),
    "float": call_of("float"),
    "str": call_of("str"),
    "len": call_of("len"),
    "range": call_of("range"),
    # 演算
    "add": binop(ast.Add),
    "sub": binop(ast.Sub),
    "mult": binop(ast.Mult),
    "div": binop(ast.Div),
    "floordiv": binop(ast.FloorDiv),
    "mod": binop(ast.Mod),
    "pow": binop(ast.Pow),
    "compare": node(ast.Compare),
    "boolop": node(ast.BoolOp),
    # 変数
    "assign": node(ast.Assign, ast.AugAssign, ast.AnnAssign),
    "augassign": node(ast.AugAssign),
    # 制御構文
    "if": node(ast.If),
    "for": node(ast.For),
    "while": node(ast.While),
    "break": node(ast.Break),
    "continue": node(ast.Continue),
    # データ構造
    "list": any_of(node(ast.List), call_of("list")),
    "tuple": any_of(node(ast.Tuple), call_of("tuple")),
    "dict": any_of(node(ast.Dict), call_of("dict")),
    "set": any_of(node(ast.Set), call_of("set")),
    "subscript": node(ast.Subscript),
    "slice": node(ast.Slice),
    "append": method_of("append"),
    # 関数
    "def": node(ast.FunctionDef),
    "return": node(ast.Return),
    # 発展的な構文（未習警告の検出用）
    "fstring": node(ast.JoinedStr),
    "comprehension": node(ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp),
    "ifexp": node(ast.IfExp),
    "lambda": node(ast.Lambda),
    "class": node(ast.ClassDef),
    "try": node(ast.Try, ast.TryStar),
    "with": node(ast.With, ast.AsyncWith),
    "import": node(ast.Import, ast.ImportFrom),
    "walrus": node(ast.NamedExpr),
    "match": node(ast.Match),
    "global": node(ast.Global, ast.Nonlocal),
    "del": node(ast.Delete),
    "assert": node(ast.Assert),
    "yield": node(ast.Yield, ast.YieldFrom),
    "async": node(ast.AsyncFunctionDef, ast.AsyncFor, ast.Await),
    "starred": node(ast.Starred),
}

_BUILTIN_NAMES = set(dir(builtins))


def used_features(tree):
    """コード中に現れる概念・組込み関数・メソッド・importの集合を返す。

    概念は "for"、組込み関数は "sum()"、メソッドは ".split()"、
    importは "import:math" の形式。
    """
    found = set()
    for n in ast.walk(tree):
        for name, pred in CONCEPTS.items():
            if pred(n):
                found.add(name)
        if isinstance(n, ast.Call):
            if isinstance(n.func, ast.Name) and n.func.id in _BUILTIN_NAMES:
                if n.func.id not in CONCEPTS:
                    found.add(f"{n.func.id}()")
            elif isinstance(n.func, ast.Attribute) and n.func.attr not in CONCEPTS:
                found.add(f".{n.func.attr}()")
        if isinstance(n, ast.Import):
            found.update(f"import:{a.name.split('.')[0]}" for a in n.names)
        elif isinstance(n, ast.ImportFrom) and n.module:
            found.add(f"import:{n.module.split('.')[0]}")
    return found


def uses(tree, concept):
    pred = CONCEPTS[concept]
    return any(pred(n) for n in ast.walk(tree))


def _block_children(n):
    """制御構文の「本体」に当たる文だけを返す（for の iter や if の条件式は含めない）。"""
    stmts = []
    for field in ("body", "orelse", "finalbody"):
        stmts.extend(getattr(n, field, []) or [])
    for h in getattr(n, "handlers", []) or []:
        stmts.extend(h.body)
    return stmts


def nested(tree, inner, outer):
    """outer 概念のブロック本体の中に inner 概念が存在するか（例: print in for）。"""
    outer_pred, inner_pred = CONCEPTS[outer], CONCEPTS[inner]
    for n in ast.walk(tree):
        if outer_pred(n):
            for stmt in _block_children(n):
                if any(inner_pred(m) for m in ast.walk(stmt)):
                    return True
    return False


def assigned_names(tree):
    return {
        n.id
        for n in ast.walk(tree)
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)
    }
