"""使い方:

    python3 -m grader assignments/01_print.yaml submissions/01/ [--out results/01_print]
"""

import argparse
import sys
from pathlib import Path

from . import config, judge, report, submission


def main(argv=None):
    p = argparse.ArgumentParser(prog="grader", description="提出コードの AUTO_PASS / NEEDS_REVIEW 判定")
    p.add_argument("config", type=Path, help="課題設定 YAML")
    p.add_argument("submissions", type=Path, help="提出 .py を置いたディレクトリ")
    p.add_argument("--out", type=Path, help="出力先（既定: results/<設定ファイル名>）")
    p.add_argument("--python", default=sys.executable, help="学生コードを実行する Python")
    args = p.parse_args(argv)

    try:
        cfg = config.load(args.config)
        judge.prepare(cfg, args.python)
    except config.ConfigError as e:
        print(f"設定エラー: {e}", file=sys.stderr)
        return 2
    if not args.submissions.is_dir():
        print(f"ディレクトリが見つからない: {args.submissions}", file=sys.stderr)
        return 2

    subs = submission.discover(args.submissions)
    graded = []
    for i, sub in enumerate(subs, 1):
        print(f"\r[{i}/{len(subs)}] {sub.filename[:60]:<60}", end="", file=sys.stderr)
        graded.append(judge.grade(sub, cfg, args.python))
    print(file=sys.stderr)

    out_dir = args.out or Path("results") / args.config.stem
    csv_path = report.write(graded, out_dir)
    print(report.summary(graded))
    print(f"CSV: {csv_path}")
    print(f"実行Python: {args.python}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
