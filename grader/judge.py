"""チェック結果の集約と最終判定。

AUTO_PASS は「全カテゴリが PASS」のときだけ。FAIL / UNKNOWN / 未実行(-) が
1つでもあれば NEEDS_REVIEW。ツール内部の例外も NEEDS_REVIEW に倒す。
"""

import traceback
from dataclasses import dataclass, field
from pathlib import Path

from . import runner, submission
from .checks import NOT_RUN, PASS, CheckResult
from .checks import dynamic, static
from .config import ConfigError

AUTO_PASS = "AUTO_PASS"
NEEDS_REVIEW = "NEEDS_REVIEW"
CATEGORIES = ["file", "syntax", "execution", "output", "requirements"]


@dataclass
class Graded:
    sub: submission.Submission
    status: str = NEEDS_REVIEW
    results: dict[str, CheckResult] = field(default_factory=dict)
    unlearned: list[str] | None = None
    records: list = field(default_factory=list)  # (TestCase, RunResult, ok)

    @property
    def issues(self):
        return [i for c in CATEGORIES if c in self.results for i in self.results[c].issues]


def _not_run(category):
    return CheckResult(category, NOT_RUN)


def _grade(g, cfg, python):
    sub = g.sub
    g.results["file"] = sub.file_check
    if sub.source is None:
        return

    tree, g.results["syntax"] = static.check_syntax(sub.source)
    if tree is None:
        return

    g.results["requirements"] = static.check_requirements(tree, cfg)
    g.unlearned = static.find_unlearned(tree, cfg.allowed)

    dangerous = static.find_dangerous(tree)
    if dangerous:
        g.results["execution"] = CheckResult("execution").unknown(
            "NOT_EXECUTED:" + ",".join(dangerous),
            f"安全のため実行せず（{', '.join(dangerous)} を使用）",
        )
        return

    execution, output, g.records = dynamic.run_tests(sub.source, cfg, python)
    nondet = static.find_nondeterministic(tree)
    if nondet:
        execution.unknown(
            "NONDETERMINISTIC", f"実行ごとに結果が変わり得る（{', '.join(nondet)}）"
        )
    g.results["execution"], g.results["output"] = execution, output


def grade(sub, cfg, python):
    g = Graded(sub)
    try:
        _grade(g, cfg, python)
    except Exception:
        g.results["file"] = CheckResult("file").unknown(
            "TOOL_ERROR", "採点ツール内部エラー: " + traceback.format_exc(limit=1).strip()
        )
    for c in CATEGORIES:
        g.results.setdefault(c, _not_run(c))
    if all(g.results[c].status == PASS for c in CATEGORIES):
        g.status = AUTO_PASS
    return g


def prepare(cfg, python):
    """模範解答で期待出力を補完し、設定を自己検証する。問題があれば ConfigError。"""
    if cfg.model_answer is not None:
        source = cfg.model_answer.read_text(encoding="utf-8")
        for i, test in enumerate(cfg.tests, 1):
            if test.expected is None:
                r = runner.run_source(source, test.stdin, cfg.timeout_sec, python)
                if r.returncode != 0 or r.timed_out or r.output_overflow:
                    raise ConfigError(f"模範解答がテスト{i}で正常終了しない:\n{r.stderr}")
                test.expected = r.stdout

        g = grade(submission.load(cfg.model_answer), cfg, python)
        if g.status != AUTO_PASS:
            reasons = "; ".join(i.message for i in g.issues)
            raise ConfigError(f"模範解答が AUTO_PASS にならない（設定を確認）: {reasons}")

    for p in cfg.should_not_pass:
        g = grade(submission.load(Path(p)), cfg, python)
        if g.status == AUTO_PASS:
            raise ConfigError(
                f"should_not_pass の {p.name} が AUTO_PASS になった（require/nesting/テストを見直す）"
            )
