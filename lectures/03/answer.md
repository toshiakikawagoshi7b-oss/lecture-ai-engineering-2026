# 第3回 解答

## 演習

- 第1回（素のLLM）とエージェントの回答の違い：【要記入：Codespaces で `uv run python -m app.agent "AIE2026の講座の宿題にある「3レベル」とは何ですか？"` を実行して比べる】
- `--trace` で見えたツール呼び出し（ツール名と引数）：【要記入：`uv run python -m app.agent --trace "LoRAとQLoRAの違いは？"` の `[tool call]` 行】
- 1つの質問での LLM 呼び出し回数（`requests`）：【要記入】
- 追加したツールと、docstring に書いた説明：
  - `make_quiz(lecture: int)`：指定した回の用語を用語集から1つ選び、「○○の意味は？」という問題と答え（定義）を JSON で返す。用語がない回（第0回など）は、問題を作れる回の一覧を返す
  - docstring：「指定した回の用語から確認問題を1問作り、問題と答えをJSONで返す。『第2回の確認問題を出して』『理解度をチェックしたい』のように、復習や確認のための問題を求められたときに使う。返ってきた answer は、利用者が答えるまで見せずに、まず question だけを出題すること」
  - `INSTRUCTIONS` にも「確認問題を求められたら make_quiz を使い、答えは利用者が回答するまで見せない」を追加

## 宿題

取り組んだレベル：基礎 / 実装 / 発展(b)（発展(a) の ADK は行っていない）

### 基礎：指示と docstring を1か所ずつ変えて比べる

- やったこと：`scripts/lec03_compare.py` で、ファイルは書き換えずに実行時に1か所だけ変えたエージェントを組み立て、同じ質問「LoRAとQLoRAの違いは？」を各条件2回ずつ実行した（モデル：gemini-3.5-flash-lite）。記録は `lectures/03/experiments/` に保存
  - 条件 base：変更なし
  - 条件 A：`INSTRUCTIONS` から「必ず search_glossary で用語集を確認する」の行を削除
  - 条件 B：`search_glossary` の docstring を「用語を1つだけ」→「関係する用語をまとめて」に変更
  - 条件 C：`INSTRUCTIONS` の「最後に第N回を示す」→「最後に確認問題を1問出す」に変更
- 結果：【要記入：実行後に下の表を埋める】

| 条件 | ツール呼び出し（回数と引数） | requests | 回答の変化 |
|---|---|---|---|
| base | | | |
| A | | | |
| B | | | |
| C | | | |

- 気づき・疑問：【要記入】
  - 補足（コードを読んで分かったこと）：`search_glossary` は検索語の空白を取り除いてから部分一致を見るため、条件 B で「LoRA QLoRA」のようにまとめて渡されても、各用語の名前が検索語に含まれていればヒットする。まとめて検索しても結果が大きく崩れないのは、プロンプトではなくツール側の実装のおかげかもしれない

### 実装：保存前に承認を挟む save_learning_log

- やったこと：
  - `app/tools.py` に `save_learning_log(title, content)` を追加。`learning_log/日時_題名.md` に保存する（日時を付けて上書きを防ぐ。`learning_log/` は `.gitignore` 済み）
  - `app/agent.py` で `agent.tool_plain(tools.save_learning_log, requires_approval=True)` と登録し、`output_type=[str, DeferredToolRequests]` に変更
  - CLI に `run_with_approval()` を追加。結果が `DeferredToolRequests` なら、保存しようとしている題名と本文を表示して y/N を聞き、承認は `True`、拒否は `ToolDenied(...)` を `DeferredToolResults` にまとめ、`message_history=result.all_messages()` と一緒に再実行する
  - `tests/test_lec03_homework.py` を追加。偽モデル（FunctionModel）に保存を依頼させ、承認したときだけファイルができ、拒否したときはできないことを API キーなしで確かめる（全19テスト通過）
- 結果：【要記入：`uv run python -m app.agent --trace "今日学んだLoRAの要点を学習ログに保存して"` で y と n を試した結果】
- 気づき・疑問：
  - 「保存の前に確認して」を指示文に書くだけでは、モデルが守るかどうかは確率的。`requires_approval=True` はコード側で必ず止まるので、取り消しにくい操作は仕組みで守るほうが確実
  - 拒否したときも、拒否した理由がツールの結果としてモデルに返るので、モデルは「保存しなかった」と利用者に説明できる
  - 【要記入：実際に動かして気づいたこと】

### 発展(b)：Pi のシステムプロンプトと比べる

- やったこと：Pi（npm 版 1.5.0）を Codespaces で動かし【要記入：試した依頼】、公開リポジトリの `system-prompt.ts` を読んで `INSTRUCTIONS` と比べた。比較の詳細は `lectures/03/pi_comparison.md`
- 結果（要点）：
  - Pi の既定のプロンプトは「コーディング支援役」の1文＋道具4つの一覧と使い方のルール＋「簡潔に」「パスを明示」だけで、仕事の中身は利用者の依頼と AGENTS.md に任せている
  - 自分の `INSTRUCTIONS` は用途が決まっているので、「どの道具をいつ使うか」「推測で断定しない」「答えはヒントで導く」まで書いている
  - Pi は確認なしで bash や write を実行し、安全は Codespaces のような使い捨て環境で守る設計。自分のエージェントは保存だけをコードで止めた
- 気づき・疑問：
  - Pi はプロンプトをセクションに分けて組み立て、変わった部分だけ差し替える。固定の文章より、状況に応じて指示を変えやすい
  - 道具の使い方のルールを、docstring とプロンプト本文のどちらに書くのが効くのかは、基礎の条件 B と合わせて追加で試したい
