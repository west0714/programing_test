"""学生コードを別プロセスで安全寄りに実行する。

本格的なサンドボックスではない。事故（無限ループ・大量出力・入力待ち）への対策が目的で、
危険な import は静的チェックで事前に弾く前提。
"""

import os
import resource
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

HARNESS = Path(__file__).with_name("harness.py")

MAX_OUTPUT = 64 * 1024  # これを超える出力は NEEDS_REVIEW
FILE_SIZE_LIMIT = 1024 * 1024  # 子プロセスが書けるファイルサイズの上限（stdout含む）


@dataclass
class RunResult:
    returncode: int | None
    stdout: str
    stderr: str
    timed_out: bool
    output_overflow: bool
    duration: float


def _limit_resources(cpu_seconds):
    def apply():
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds + 1))
        resource.setrlimit(resource.RLIMIT_FSIZE, (FILE_SIZE_LIMIT, FILE_SIZE_LIMIT))
        resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))

    return apply


def _read_capped(f):
    f.seek(0)
    data = f.read(MAX_OUTPUT + 1)
    overflow = len(data) > MAX_OUTPUT
    return data[:MAX_OUTPUT].decode("utf-8", errors="replace"), overflow


def run_source(source, stdin="", timeout=3.0, python=sys.executable):
    """ソース文字列を一時ディレクトリで実行する。"""
    workdir = Path(tempfile.mkdtemp(prefix="grader_"))
    try:
        script = workdir / "submission.py"
        script.write_text(source, encoding="utf-8")
        with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
            start = time.monotonic()
            proc = subprocess.Popen(
                [python, "-I", "-X", "utf8", str(HARNESS), str(script)],
                stdin=subprocess.PIPE,
                stdout=out,
                stderr=err,
                cwd=workdir,
                env={"PATH": "/usr/bin:/bin", "LANG": "en_US.UTF-8"},
                start_new_session=True,
                preexec_fn=_limit_resources(int(timeout) + 1),
            )
            timed_out = False
            try:
                proc.communicate(stdin.encode("utf-8"), timeout=timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                proc.wait()
            duration = time.monotonic() - start
            stdout, out_overflow = _read_capped(out)
            stderr, err_overflow = _read_capped(err)
        # CPU制限超過(SIGXCPU)はタイムアウト扱い、ファイルサイズ超過(SIGXFSZ)は出力過多扱い
        rc = proc.returncode
        if rc == -signal.SIGXCPU:
            timed_out = True
        overflow = out_overflow or err_overflow or rc == -signal.SIGXFSZ
        return RunResult(rc, stdout, stderr, timed_out, overflow, duration)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
