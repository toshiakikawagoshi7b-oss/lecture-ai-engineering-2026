# 第3回 宿題・発展(b)：Pi のシステムプロンプトと INSTRUCTIONS の比較

対象：`earendil-works/pi` の `packages/coding-agent/src/core/system-prompt.ts`（2026-11-08 時点 `7d07332`、npm 版 1.5.0）と、
このリポジトリの `app/agent.py` の `INSTRUCTIONS`。

## 1. Pi の既定のシステムプロンプト（組み立て後の形）

Pi のシステムプロンプトは固定の文章ではなく、`buildSystemPromptSections()` が部品を組み立てて作る。
既定の4ツール（read・bash・edit・write）のときは、おおよそ次の形になる（docs のパスはインストール先で変わる）。

```text
You are a coding assistant running inside pi, a coding agent harness. Help users inspect files, run commands, and modify code.
<tools>
- read: Read file contents
- bash: Execute bash commands (ls, grep, find, etc.)
- edit: Make precise file edits with exact text replacement, including multiple disjoint edits in one call
- write: Create or overwrite files

Additional tools may be available.
</tools>
<rules>
- Use bash for file operations like ls, rg, find
- Use read to examine files instead of cat or sed.
- You can inspect PI_* environment variables for current model and session details.
- Use edit for targeted changes. Batch changes to one file in a single call.
- Each edits[].oldText must exactly and uniquely match the original file. Keep matches short and non-overlapping; ...
- Use write only for new files or complete rewrites.
- Be concise in your responses
- Show file paths clearly when working with files
</rules>
<docs>
Pi documentation (read only when the user asks about the harness itself, ...):
- Main documentation: .../README.md  ...（どの話題ならどの docs を読むかの対応表）
</docs>
<project_context>   ← 作業フォルダに AGENTS.md などがあれば、その中身がここに入る
<skills>            ← スキルがあれば一覧
<cwd>
/workspaces/lecture-ai-engineering-2026
</cwd>
```

日本語にすると「あなたは Pi の中で動くコーディング支援役。ファイルを見て、コマンドを実行し、コードを直す」
＋道具の一覧＋道具ごとの使い方のルール＋「簡潔に答える」「ファイルパスを明示する」だけである。

## 2. 何が書かれていて、何が書かれていないか

| 観点 | Pi | 自分の INSTRUCTIONS |
|---|---|---|
| 役割 | 「コーディング支援役」の1文 | 「AIE2026 の学習支援エージェント」の1文 |
| 道具の一覧 | プロンプト本文に1行ずつ列挙（`<tools>`） | 書かない。docstring がツール定義としてモデルに渡る |
| 道具の使い方 | 道具ごとに短いルール（read は cat の代わり、edit は一意に一致させる、等） | 「答える前に必ず search_glossary」「回の内容は get_lecture_summary」など、**いつ使うか**を書く |
| 正しさの担保 | 書かない（ファイルを読めば事実が手に入る前提） | 「用語集にないことは推測で断定しない」と明記 |
| 回答の形式 | 「簡潔に」「パスを明示」 | 「最後に第N回を示す」 |
| 教育的な配慮 | なし | 「宿題の答えは書かずヒントで導く」 |
| 安全・確認 | **書かない**。確認なしで bash や write を実行する | 保存は `requires_approval=True` でコード側が止める（指示文ではなく仕組みで担保） |
| 利用者・状況ごとの追加 | AGENTS.md・スキル・作業フォルダを差し込む部品がある | なし（固定の文章） |
| 長さ | 既定部分で十数行。足りない分は docs を「必要なときだけ読め」と案内 | 7行 |

## 3. 違いが生まれる理由（考察）

1. **汎用か、用途特化か。** Pi は何の作業を頼まれるか分からないので、プロンプトには「道具の正しい使い方」だけを書き、
   仕事の中身は利用者の依頼と AGENTS.md に任せている。学習支援エージェントは仕事が決まっているので、
   「どの道具をどの場面で使うか」「答えてはいけないこと」まで指示に書ける。
2. **事実の出どころが違う。** Pi はファイルやコマンド結果という「確かめられる事実」を自分で取りに行けるので、
   「推測で答えるな」と書かなくても、読めば分かる。学習支援エージェントは用語集にない問いでは
   LLM の知識に頼りがちなので、「用語集にないと伝える」というルールが必要になる。
3. **安全をどこで守るか。** Pi は指示文にも仕組みにも確認を入れず、「Codespaces のような使い捨て環境で動かす」ことで
   安全を守る設計。自分のエージェントは、取り消しにくい保存だけを**コードで**止めた（宿題・実装）。
   指示文に「保存前に確認して」と書くだけでは、モデルが守らない可能性が残るためである。
4. **プロンプトを部品で組み立てる工夫。** Pi はセクション（`<tools>` `<rules>` など）に分け、変わった部品だけを
   差し替えられるようにしている（`diffSystemPromptSections`）。会話の途中で道具やルールが変わっても、
   全体を作り直さずに済む。固定の `INSTRUCTIONS` にはない発想。
5. **道具の説明文の置き場所。** Pi は道具の一覧と使い方をプロンプト本文にも書いている。
   自分のエージェントは使い方のルールを docstring だけに書いている。宿題・基礎の条件B（docstring の変更）の結果と合わせて、
   「道具の使い方のルールは、道具の説明文とプロンプト本文のどちらに書くのが効くか」を試す価値がある。

## 4. 自分の INSTRUCTIONS に取り入れられそうなこと

- 「簡潔に答える」のような出力の長さの指定（Pi は明記している）
- 道具ごとの「やってはいけない使い方」（Pi の「cat ではなく read を使う」に相当するもの。例：「search_glossary に文章をそのまま入れない」）
- 講座の回や利用者の状況に応じて部品を差し込む仕組み（Pi の project_context に相当）
