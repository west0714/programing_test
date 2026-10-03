"""課題設定（YAML）の読込・検証・デフォルト補完。"""

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .concepts import CONCEPTS

MODES = {"stdout", "stdin_stdout", "function"}
KNOWN_KEYS = {
    "name", "mode", "timeout_sec", "model_answer", "should_not_pass", "tests",
    "require", "nesting", "variables", "forbid", "allowed_level", "levels_file",
}


class ConfigError(Exception):
    pass


@dataclass
class TestCase:
    stdin: str
    expected: str | None  # None なら模範解答から生成


@dataclass
class Assignment:
    name: str
    path: Path
    mode: str = "stdout"
    timeout_sec: float = 3.0
    model_answer: Path | None = None
    should_not_pass: list[Path] = field(default_factory=list)
    tests: list[TestCase] = field(default_factory=list)
    require: list[str] = field(default_factory=list)
    nesting: list[tuple[str, str]] = field(default_factory=list)  # (inner, outer)
    variables: list[str] = field(default_factory=list)
    forbid: list[str] = field(default_factory=list)
    allowed: set[str] | None = None  # 未習警告用の許可リスト（None なら判定しない）


def _str_list(raw, key):
    value = raw.get(key) or []
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise ConfigError(f"{key} は文字列のリストで書いてください")
    return value


def _check_concepts(names, key):
    unknown = [n for n in names if n not in CONCEPTS]
    if unknown:
        raise ConfigError(
            f"{key} に未定義の概念: {unknown}（grader/concepts.py の CONCEPTS に追加してください）"
        )


def _load_allowed(levels_path, level):
    if not levels_path.exists():
        raise ConfigError(f"levels ファイルが見つからない: {levels_path}")
    data = yaml.safe_load(levels_path.read_text(encoding="utf-8")) or {}
    levels = data.get("levels") or {}
    if level not in levels:
        raise ConfigError(f"{levels_path} に allowed_level {level} の定義がない")
    allowed = set()
    for lv in sorted(k for k in levels if k <= level):  # 累積
        allowed.update(str(x) for x in levels[lv] or [])
    return allowed


def load(path):
    path = Path(path)
    base = path.parent
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        raise ConfigError(f"YAMLとして読めない: {e}") from e
    if not isinstance(raw, dict):
        raise ConfigError("設定ファイルの中身が空、または形式が違う")
    extra = set(raw) - KNOWN_KEYS
    if extra:
        raise ConfigError(f"未知のキー（綴りミス？）: {sorted(extra)}")

    cfg = Assignment(name=str(raw.get("name") or path.stem), path=path)

    cfg.mode = raw.get("mode", "stdout")
    if cfg.mode not in MODES:
        raise ConfigError(f"mode は {sorted(MODES)} のいずれか")
    if cfg.mode == "function":
        raise ConfigError("mode: function はまだ実装されていない")

    cfg.timeout_sec = float(raw.get("timeout_sec", 3))
    if raw.get("model_answer"):
        cfg.model_answer = base / raw["model_answer"]
        if not cfg.model_answer.exists():
            raise ConfigError(f"模範解答が見つからない: {cfg.model_answer}")
    cfg.should_not_pass = [base / p for p in _str_list(raw, "should_not_pass")]
    for p in cfg.should_not_pass:
        if not p.exists():
            raise ConfigError(f"should_not_pass のファイルが見つからない: {p}")

    raw_tests = raw.get("tests") or [{}]  # stdout 型なら tests 省略可（入力なし1件）
    if not isinstance(raw_tests, list):
        raise ConfigError("tests はリストで書いてください")
    for i, t in enumerate(raw_tests, 1):
        t = t or {}
        stdin, expected = t.get("stdin", ""), t.get("expected")
        # YAML では `stdin: 5` が数値になるので文字列を強制する
        if not isinstance(stdin, str):
            raise ConfigError(f'tests[{i}].stdin は文字列で（例: stdin: "5"）')
        if expected is not None and not isinstance(expected, str):
            raise ConfigError(f'tests[{i}].expected は文字列で（例: expected: "3"）')
        if stdin and not stdin.endswith("\n"):
            stdin += "\n"
        if expected is None and cfg.model_answer is None:
            raise ConfigError(f"tests[{i}] に expected も model_answer もない")
        cfg.tests.append(TestCase(stdin, expected))
    if cfg.mode == "stdout" and any(t.stdin for t in cfg.tests):
        raise ConfigError("mode: stdout では stdin を指定できない（stdin_stdout を使う）")

    cfg.require = _str_list(raw, "require")
    _check_concepts(cfg.require, "require")
    cfg.forbid = _str_list(raw, "forbid")
    _check_concepts(cfg.forbid, "forbid")
    cfg.variables = _str_list(raw, "variables")
    for spec in _str_list(raw, "nesting"):
        parts = spec.split(" in ")
        if len(parts) != 2:
            raise ConfigError(f'nesting は "print in for" の形式で: {spec!r}')
        inner, outer = (p.strip() for p in parts)
        _check_concepts([inner, outer], "nesting")
        cfg.nesting.append((inner, outer))

    if raw.get("allowed_level") is not None:
        levels_path = base / raw.get("levels_file", "levels.yaml")
        cfg.allowed = _load_allowed(levels_path, int(raw["allowed_level"]))
    return cfg
