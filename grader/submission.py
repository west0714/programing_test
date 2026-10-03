"""提出ファイルの列挙・学籍番号抽出・デコード。

想定外のファイルも黙って捨てず、問題（issues）付きで返す。
"""

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from .checks import CheckResult

# 例: "t99001tt 山田　太郎_9999001_assignsubmission_file_01rensyuT99001.py"
#   学籍番号 = 先頭の空白までの t99001tt（学部により g99002gg などもある）
#   提出番号 = 9999001（提出システム側の番号）
STUDENT_ID_RE = re.compile(r"^(\S+)\s")
SUBMISSION_NO_RE = re.compile(r"_(\d+)_assignsubmission_file_")


@dataclass
class Submission:
    path: Path
    filename: str
    student_id: str
    submission_no: str
    source: str | None
    file_check: CheckResult = field(default_factory=lambda: CheckResult("file"))


def decode(data, check):
    """UTF-8（BOM可）を正とし、cp932 で読めた場合は要確認扱いにする。"""
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        pass
    try:
        text = data.decode("cp932")
        check.unknown("ENCODING_CP932", "文字コードがShift_JIS（UTF-8ではない）")
        return text
    except UnicodeDecodeError:
        check.unknown("ENCODING_UNKNOWN", "文字コードを判別できない")
        return None


def load(path):
    # macOS では zip 展開したファイル名が NFD になることがあるので NFC に揃える
    filename = unicodedata.normalize("NFC", path.name)
    m = STUDENT_ID_RE.match(filename)
    n = SUBMISSION_NO_RE.search(filename)
    sub = Submission(
        path,
        filename,
        m.group(1) if m else "",
        n.group(1) if n else "",
        None,
    )
    if path.suffix.lower() != ".py":
        sub.file_check.unknown("NOT_PY", f"拡張子が .py ではない（{path.suffix or 'なし'}）")
        return sub
    sub.source = decode(path.read_bytes(), sub.file_check)
    return sub


def discover(directory):
    directory = Path(directory)
    paths = sorted(
        p for p in directory.iterdir() if p.is_file() and not p.name.startswith(".")
    )
    subs = [load(p) for p in paths]
    counts = Counter(s.student_id for s in subs if s.student_id)
    for s in subs:
        if s.student_id and counts[s.student_id] > 1:
            s.file_check.unknown("MULTIPLE_FILES", "同じ学籍番号の提出が複数ある")
    return subs
