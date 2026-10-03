# Python演習 採点支援ツール（MVP）

提出された `.py` を **AUTO_PASS**（目視確認を省略してよい）と **NEEDS_REVIEW**（TA・教員が確認）に振り分けます。
自動で不合格にはしません。少しでも確信できない提出はすべて NEEDS_REVIEW になります。

## 使い方

```sh
pip install pyyaml        # 依存はこれだけ（Python 3.11+）
python3 -m grader assignments/01_print.yaml submissions/01/
```

- 結果: `results/01_print/result.csv`（一覧）と `results/01_print/details/<学籍番号>.txt`（全出力）
- TA は CSV を `status = NEEDS_REVIEW` で絞り込んで確認する
- `unlearned` 列は未習要素の**警告のみ**（判定には影響しない）
- `submissions/` と `results/` は個人情報を含むため `.gitignore` 済み。コミットしないこと

## 判定の仕組み

| カテゴリ | 内容 |
|---|---|
| file | 拡張子・文字コード（UTF-8以外は要確認）・同一学籍番号の複数提出 |
| syntax | 空ファイル・SyntaxError |
| execution | 実行時エラー・タイムアウト・出力過多・標準エラー出力・危険な import（実行しない）・random 等 |
| output | テストケースごとの標準出力比較（行末空白と末尾空行のみ無視） |
| requirements | `require` / `nesting` / `variables` / `forbid` |

全カテゴリが PASS のときだけ AUTO_PASS。`input()` のプロンプト文字列は出力されない扱い。

## 課題設定（`assignments/*.yaml`）

```yaml
name: （例）for文 1からnまで表示
mode: stdin_stdout            # stdout | stdin_stdout
model_answer: ../model/xx/answer.py
should_not_pass: [../model/xx/ng_hardcode.py]
tests:
  - stdin: "5"                # expected 省略時は模範解答の出力を使う
  - stdin: "3"
require: [input, int, for, print]
nesting: ["print in for"]
variables: []                 # 代入されているべき変数名
forbid: []
allowed_level: 3              # levels.yaml の回（未習警告用）
```

- 起動時に**模範解答が AUTO_PASS になるか**、`should_not_pass` の例が **AUTO_PASS にならないか**を検証し、ダメなら設定エラーで止まる
- ハードコード対策には「入力を変えた複数テスト」と `nesting` が有効
- 使える概念名は [grader/concepts.py](grader/concepts.py) の `CONCEPTS`。新しい学習要素は1行追加する
- 授業ごとの既習要素は [assignments/levels.yaml](assignments/levels.yaml) に追記する

## テスト

```sh
python3 -m unittest discover tests
```

## 未対応（MVP外）

関数型課題（`mode: function`）、模範解答との類似度、データフロー解析、GUI/DB/LLM、本格サンドボックス。