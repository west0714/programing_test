"""チェック結果の共通型。

各チェックは CheckResult を返す。status は 3値（PASS / FAIL / UNKNOWN）で、
UNKNOWN（判定不能・ツール側の問題）は FAIL と同様に AUTO_PASS を妨げる。
"""

from dataclasses import dataclass, field

PASS = "PASS"
FAIL = "FAIL"
UNKNOWN = "UNKNOWN"
NOT_RUN = "-"


@dataclass
class Issue:
    code: str  # 機械可読（例: MISSING:for）
    message: str  # TA向けの日本語説明


@dataclass
class CheckResult:
    category: str  # file / syntax / execution / output / requirements
    status: str = PASS
    issues: list[Issue] = field(default_factory=list)

    def fail(self, code, message):
        self.issues.append(Issue(code, message))
        self.status = FAIL if self.status != UNKNOWN else UNKNOWN
        return self

    def unknown(self, code, message):
        self.issues.append(Issue(code, message))
        self.status = UNKNOWN
        return self
