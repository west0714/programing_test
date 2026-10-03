"""CSV（一覧）と details（学生ごとの全出力）の書き出し。"""

import csv
from collections import Counter

from .judge import AUTO_PASS, CATEGORIES, NEEDS_REVIEW

COLUMNS = [
    "student_id", "submission_no", "filename", "status", "reason_codes", "reason",
    *CATEGORIES, "unlearned", "failed_tests", "stdout_head", "stderr_tail",
]


def _escape(text, limit, tail=False):
    text = text[-limit:] if tail else text[:limit]
    return text.replace("\\", "\\\\").replace("\n", "\\n")


def _row(g):
    issues = g.issues
    tested = [ok for _, _, ok in g.records]
    first = g.records[0][1] if g.records else None
    return {
        "student_id": g.sub.student_id,
        "submission_no": g.sub.submission_no,
        "filename": g.sub.filename,
        "status": g.status,
        "reason_codes": ";".join(i.code for i in issues),
        "reason": " / ".join(i.message for i in issues),
        **{c: g.results[c].status for c in CATEGORIES},
        "unlearned": "-" if g.unlearned is None else ";".join(g.unlearned),
        "failed_tests": f"{sum(ok is not True for ok in tested)}/{len(tested)}" if tested else "-",
        "stdout_head": _escape(first.stdout, 200) if first else "",
        "stderr_tail": _escape(first.stderr, 200, tail=True) if first else "",
    }


def _details(g):
    lines = [f"file: {g.sub.filename}", f"status: {g.status}", ""]
    for i in g.issues:
        lines.append(f"- [{i.code}] {i.message}")
    if g.unlearned:
        lines.append(f"- [警告] 未習の可能性: {', '.join(g.unlearned)}")
    for n, (test, r, ok) in enumerate(g.records, 1):
        lines += [
            "", f"=== テスト{n}: {'一致' if ok else '不一致/未判定'} "
            f"(rc={r.returncode}, {r.duration:.2f}s{', timeout' if r.timed_out else ''}) ===",
            "--- stdin ---", test.stdin,
            "--- expected ---", test.expected or "",
            "--- stdout ---", r.stdout,
            "--- stderr ---", r.stderr,
        ]
    return "\n".join(lines) + "\n"


def write(graded, out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    details_dir = out_dir / "details"
    details_dir.mkdir(exist_ok=True)
    csv_path = out_dir / "result.csv"
    # utf-8-sig: macOS の Excel / Numbers で文字化けしないよう BOM を付ける
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        for g in graded:
            w.writerow(_row(g))
    for g in graded:
        stem = g.sub.student_id or g.sub.path.stem
        (details_dir / f"{stem}.txt").write_text(_details(g), encoding="utf-8")
    return csv_path


def summary(graded):
    statuses = Counter(g.status for g in graded)
    codes = Counter(i.code.split(":")[0] for g in graded for i in g.issues)
    lines = [
        f"合計 {len(graded)} 件: {AUTO_PASS} {statuses[AUTO_PASS]} / "
        f"{NEEDS_REVIEW} {statuses[NEEDS_REVIEW]}"
    ]
    for code, n in codes.most_common():
        lines.append(f"  {code}: {n}")
    unlearned = sum(1 for g in graded if g.unlearned)
    if unlearned:
        lines.append(f"  （警告）未習要素の使用: {unlearned} 件")
    return "\n".join(lines)
