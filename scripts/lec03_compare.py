"""第3回 宿題・基礎：指示（INSTRUCTIONS）やツールの説明文を「1か所だけ」変えて、ふるまいを比べる。

app/agent.py や app/tools.py のファイルは書き換えず、実行時に変更版のエージェントを組み立てる。
ツールの関数そのもの（中身の処理）は同じで、モデルに渡す文章だけが違う。

使い方（Codespaces で。GEMINI_API_KEY が必要）:
    uv run python scripts/lec03_compare.py                       # 全条件を1回ずつ
    uv run python scripts/lec03_compare.py --repeat 2            # 揺れを見るため各2回
    uv run python scripts/lec03_compare.py --only base A         # 条件を選ぶ
    uv run python scripts/lec03_compare.py --question "RAGとは？"

結果は画面に出し、lectures/03/experiments/ に Markdown で保存する。
無料枠のレート制限に当たらないよう、実行の間に待ち時間（--wait 秒）を入れる。
"""

import argparse
import inspect
import time
from datetime import datetime
from pathlib import Path

from pydantic_ai import Agent, DeferredToolRequests, Tool
from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.messages import ToolCallPart

from app import tools
from app.agent import INSTRUCTIONS, build_model
from app.config import MODEL, api_error_message

OUT_DIR = Path(__file__).resolve().parent.parent / "lectures" / "03" / "experiments"
DEFAULT_QUESTION = "LoRAとQLoRAの違いは？"

LINE_MUST_SEARCH = "- 用語や講座に固有のことを答える前に、必ず search_glossary で用語集を確認する。\n"
LINE_LECTURE = "- 回答の最後に、関係する回（第N回）を示す。\n"
SEARCH_DOC = inspect.cleandoc(tools.search_glossary.__doc__)
ONE_TERM = "query には調べたい用語を1つだけ入れる（例: \"LoRA\"）。"

# 条件ごとに「何を・どう変えたか」と、変更後の指示・説明文。変えるのは1か所だけ
VARIANTS = {
    "base": {
        "label": "変更なし（基準）",
        "instructions": INSTRUCTIONS,
        "search_doc": SEARCH_DOC,
    },
    "A": {
        "label": "INSTRUCTIONS から「必ず search_glossary で用語集を確認する」の行を削除",
        "instructions": INSTRUCTIONS.replace(LINE_MUST_SEARCH, ""),
        "search_doc": SEARCH_DOC,
    },
    "B": {
        "label": "search_glossary の説明文を「用語を1つだけ」→「関係する用語をまとめて」に変更",
        "instructions": INSTRUCTIONS,
        "search_doc": SEARCH_DOC.replace(
            ONE_TERM, "query には関係する用語をまとめて入れる（例: \"LoRA QLoRA 量子化\"）。"),
    },
    "C": {
        "label": "INSTRUCTIONS の「最後に第N回を示す」→「最後に確認問題を1問出す」に変更",
        "instructions": INSTRUCTIONS.replace(LINE_LECTURE, "- 回答の最後に、確認問題を1問出す。\n"),
        "search_doc": SEARCH_DOC,
    },
}


def build_variant(spec: dict) -> Agent:
    """変更版のエージェント。ツールの処理は同じで、モデルに渡す文章だけを差し替える。"""
    return Agent(
        instructions=spec["instructions"],
        output_type=[str, DeferredToolRequests],
        tools=[
            Tool(tools.search_glossary, description=spec["search_doc"]),
            Tool(tools.get_lecture_summary),
            Tool(tools.make_quiz),
        ],
    )


def run_once(name: str, spec: dict, question: str) -> str:
    result = build_variant(spec).run_sync(question, model=build_model())
    calls = [p for m in result.all_messages() for p in m.parts if isinstance(p, ToolCallPart)]
    lines = [f"### 条件 {name}：{spec['label']}", ""]
    lines.append(f"- ツール呼び出し（{len(calls)} 回）：")
    lines += [f"  - `{c.tool_name}({c.args})`" for c in calls] or ["  - なし"]
    lines.append(f"- LLM 呼び出し回数（requests）：{result.usage.requests}")
    lines.append(f"- トークン：入力 {result.usage.input_tokens} / 出力 {result.usage.output_tokens}")
    lines += ["- 回答：", "", "```text", str(result.output).strip(), "```", ""]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="第3回 宿題・基礎の比較実験")
    parser.add_argument("--question", default=DEFAULT_QUESTION)
    parser.add_argument("--only", nargs="*", choices=list(VARIANTS), help="実行する条件")
    parser.add_argument("--repeat", type=int, default=1, help="各条件の実行回数")
    parser.add_argument("--wait", type=float, default=15, help="実行の間の待ち時間（秒）")
    args = parser.parse_args()

    names = args.only or list(VARIANTS)
    report = [f"# 第3回 基礎 比較実験（{datetime.now():%Y-%m-%d %H:%M}）", "",
              f"- モデル：{MODEL}", f"- 質問：{args.question}", ""]
    first = True
    for name in names:
        for i in range(args.repeat):
            if not first:
                time.sleep(args.wait)
            first = False
            print(f"\n=== 条件 {name}（{i + 1}/{args.repeat}）===")
            try:
                block = run_once(name, VARIANTS[name], args.question)
            except ModelHTTPError as e:
                block = f"### 条件 {name}：エラー\n\n{api_error_message(e.status_code, str(e.body)[:200])}\n"
            if args.repeat > 1:
                block = block.replace("\n", f"（{i + 1}回目）\n", 1)
            print(block)
            report.append(block)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"{datetime.now():%Y%m%d_%H%M%S}.md"
    out.write_text("\n".join(report), encoding="utf-8")
    print(f"\n保存しました: {out.relative_to(Path.cwd()) if out.is_relative_to(Path.cwd()) else out}")


if __name__ == "__main__":
    main()
