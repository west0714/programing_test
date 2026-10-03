"""子プロセス側で学生コードを実行するハーネス。

    python -I -X utf8 harness.py <student.py>

- input() のプロンプト文字列を出力しない版に差し替える（出力比較を安定させるため）
- トレースバックは学生ファイル内のフレームだけを表示する

このファイルは grader パッケージを import せず、単体で動くこと。
"""

import builtins
import runpy
import sys
import traceback


def _quiet_input(prompt=""):
    line = sys.stdin.readline()
    if not line:
        raise EOFError("EOF when reading a line")
    return line.rstrip("\r\n")


def main():
    path = sys.argv[1]
    builtins.input = _quiet_input
    sys.argv = [path]
    try:
        runpy.run_path(path, run_name="__main__")
    except SystemExit:
        raise
    except BaseException as e:
        tb = e.__traceback__
        while tb is not None and tb.tb_frame.f_code.co_filename != path:
            tb = tb.tb_next
        sys.stdout.flush()
        traceback.print_exception(type(e), e, tb)
        sys.exit(1)


if __name__ == "__main__":
    main()
