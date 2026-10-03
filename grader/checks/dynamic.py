"""実行テスト（「何が起きたか」）。"""

from .. import runner
from . import CheckResult


def normalize_output(text):
    """行末空白と末尾の空行だけを無視する。それ以外（全角/半角、3 と 3.0 等）は区別する。"""
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").split("\n")]
    while lines and lines[-1] == "":
        lines.pop()
    return lines


def _error_name(stderr):
    """トレースバック最終行から例外名を取り出す（例: NameError）。"""
    lines = [l for l in stderr.strip().splitlines() if l.strip()]
    if not lines:
        return "UnknownError"
    return lines[-1].split(":")[0].strip() or "UnknownError"


def run_tests(source, cfg, python):
    """全テストケースを実行し (execution結果, output結果, 各テストの記録) を返す。"""
    execution = CheckResult("execution")
    output = CheckResult("output")
    records = []
    for i, test in enumerate(cfg.tests, 1):
        r = runner.run_source(source, test.stdin, cfg.timeout_sec, python)
        ok = None
        if r.timed_out:
            execution.fail("TIMEOUT", f"テスト{i}: タイムアウト（{cfg.timeout_sec}秒）")
        elif r.output_overflow:
            execution.fail("OUTPUT_TOO_LARGE", f"テスト{i}: 出力が大きすぎる")
        elif r.returncode != 0:
            name = _error_name(r.stderr)
            execution.fail(f"RUNTIME_ERROR:{name}", f"テスト{i}: 実行時エラー {name}")
        else:
            if r.stderr.strip():
                execution.unknown("STDERR_OUTPUT", f"テスト{i}: 標準エラー出力あり")
            ok = normalize_output(r.stdout) == normalize_output(test.expected)
            if not ok:
                output.fail(f"WRONG_OUTPUT:{i}", f"テスト{i}: 出力が期待と異なる")
        records.append((test, r, ok))

    if all(ok is None for _, _, ok in records):
        output.status = "-"  # 1件も正常終了していない
    return execution, output, records
