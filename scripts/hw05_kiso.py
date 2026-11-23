"""第5回 演習（STEP1〜5）＋宿題（基礎）をまとめて実行し、記録を残す補助スクリプト。

使い方（Codespaces の lec05 ブランチで）:
    uv run python -m scripts.hw05_kiso

やること:
  1. 変更前（RAG_TOP_K = 5）: 演習の4方式（全文投入・ベクトル検索・Tree・Graph）と、
     宿題の比較用3問をベクトル検索で実行する
  2. app/config.py の RAG_TOP_K を 5 → 2 に書き換える（宿題の「1か所の変更」）
  3. 変更後（RAG_TOP_K = 2）: 同じ3問をもう一度実行する

app/agent.py の --trace と同じ処理（agent / build_model / print_trace）を呼び、
加えて「ツールが実際に返したページ」を一覧にする。app/ 配下で変えるのは RAG_TOP_K だけ。
記録は lectures/05/hw_logs/ に、実行ごとのログ（.txt）と results.json として残す。
レート制限で止まった場合は、もう一度実行すると済んだ分を飛ばして続きから再開する。
"""

import argparse
import contextlib
import io
import json
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "app/config.py"
LOG_DIR = ROOT / "lectures/05/hw_logs"
RESULTS = LOG_DIR / "results.json"
BEFORE_K, AFTER_K = 5, 2

Q1 = "第2回の説明では、LoRAは何を固定し何を学習しますか？ QLoRAは何を加えますか？"
Q2 = ("第3回の例では、コンパクションとセッションをまたぐメモリはどう違いますか。"
      "日々のメモはすべて長期メモリに入りますか")
Q3 = "今回作ったRAGの実測平均応答時間と正答率を教えてください"
SEARCH_QUERY = "LoRA QLoRA 違い"

# (ラベル, 方式, 質問)。方式 search は、エージェントを使わない検索だけの実行。
BEFORE_RUNS = [
    ("ex_full", "full", Q1),
    ("ex_search_k5", "search", SEARCH_QUERY),
    ("q1_vector_k5", "vector", Q1),
    ("ex_tree", "tree", Q1),
    ("ex_graph", "graph", Q1),
    ("q2_vector_k5", "vector", Q2),
    ("q3_vector_k5", "vector", Q3),
]
AFTER_RUNS = [
    ("hw_search_k2", "search", SEARCH_QUERY),
    ("q1_vector_k2", "vector", Q1),
    ("q2_vector_k2", "vector", Q2),
    ("q3_vector_k2", "vector", Q3),
]


def current_top_k() -> int:
    return int(re.search(r"^RAG_TOP_K = (\d+)$", CONFIG.read_text(encoding="utf-8"), re.M).group(1))


def set_top_k(old: int, new: int) -> None:
    text = CONFIG.read_text(encoding="utf-8")
    changed, count = re.subn(rf"^RAG_TOP_K = {old}$", f"RAG_TOP_K = {new}", text, flags=re.M)
    if count != 1:
        raise SystemExit(f"app/config.py に「RAG_TOP_K = {old}」の行が1つだけある状態で実行してください。")
    CONFIG.write_text(changed, encoding="utf-8")


def load_results() -> dict:
    return json.loads(RESULTS.read_text(encoding="utf-8")) if RESULTS.exists() else {}


def save_result(label: str, record: dict, log: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    (LOG_DIR / f"{label}.txt").write_text(log, encoding="utf-8")
    results = load_results()
    results[label] = record
    RESULTS.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def page_ref(page: dict) -> dict:
    ref = {"lecture": page.get("lecture"), "page": page.get("page"), "title": page.get("title")}
    if "distance" in page:
        ref["distance"] = round(page["distance"], 4)
    if "hops" in page:
        ref["hops"] = page["hops"]
    return ref


def pages_in(tool_name: str, content: str) -> list[dict]:
    """ツールの戻り値（JSON文字列）から、本文つきで返されたページを取り出す。"""
    try:
        data = json.loads(content)
    except (TypeError, ValueError):
        return []
    if tool_name == "search_materials":
        return [page_ref(p) for p in data.get("results", [])]
    if tool_name == "search_graph":
        return [page_ref(p) for p in data.get("seeds", []) + data.get("expanded", [])]
    if tool_name == "browse_tree":
        node = data.get("node", {})
        return [page_ref(node)] if node.get("kind") == "page" else []
    return []


def run_agent(mode: str, question: str) -> tuple[dict, str]:
    """app.agent の main() と同じ流れで1回実行し、記録と表示内容を返す。"""
    from pydantic_ai.exceptions import ModelHTTPError
    from pydantic_ai.messages import ToolCallPart, ToolReturnPart

    from app import agent as A
    from app import tools
    from app.config import MODEL, RAG_TOP_K
    from app.retrieval import run_full_context

    out = io.StringIO()
    record = {"mode": mode, "question": question, "model": MODEL, "rag_top_k": RAG_TOP_K}

    def override():
        if mode == "tree":
            return A.agent.override(instructions=A.TREE_INSTRUCTIONS, tools=[tools.browse_tree])
        if mode == "graph":
            return A.agent.override(instructions=A.GRAPH_INSTRUCTIONS, tools=[tools.search_graph])
        return contextlib.nullcontext()

    for attempt in range(4):
        started = time.perf_counter()
        try:
            with override(), contextlib.redirect_stdout(out):
                print(f"[model] {MODEL}\n[mode] {mode} / RAG_TOP_K = {RAG_TOP_K}\n[question] {question}\n")
                if mode == "full":
                    result = run_full_context(
                        A.agent, question, A.build_model(),
                        instructions=A.FULL_CONTEXT_INSTRUCTIONS, prompt_template=A.FULL_CONTEXT_PROMPT,
                    )
                else:
                    result = A.agent.run_sync(question, model=A.build_model())
            break
        except ModelHTTPError as e:
            if e.status_code in (429, 503) and attempt < 3:
                print(f"  API {e.status_code}。65秒待って再試行します（{attempt + 1}/3）")
                time.sleep(65)
                continue
            record["error"] = f"HTTP {e.status_code}: {str(e.body)[:300]}"
            return record, out.getvalue() + f"\n[error] {record['error']}\n"
        except SystemExit:  # 全文投入は入力上限などのAPIエラーで終了する
            record["error"] = out.getvalue().strip().splitlines()[-1][:400]
            return record, out.getvalue()
    elapsed = time.perf_counter() - started

    calls, pending = [], {}
    for message in result.all_messages():
        for part in message.parts:
            if isinstance(part, ToolCallPart):
                pending[part.tool_call_id] = {"tool": part.tool_name, "args": part.args_as_dict(), "pages": []}
                calls.append(pending[part.tool_call_id])
            elif isinstance(part, ToolReturnPart) and part.tool_call_id in pending:
                pending[part.tool_call_id]["pages"] = pages_in(part.tool_name, part.content)

    with contextlib.redirect_stdout(out):
        print(result.output)
        A.print_trace(result, elapsed)
        print("\n--- ツールが返したページ（本文つき）---")
        for i, call in enumerate(calls, 1):
            print(f"{i}. {call['tool']}({json.dumps(call['args'], ensure_ascii=False)})")
            for p in call["pages"]:
                extra = "".join(f" / {k}={p[k]}" for k in ("distance", "hops") if k in p)
                print(f"     第{p['lecture']}回 p.{p['page']} {p['title']}{extra}")

    usage = result.usage
    record.update({
        "answer": result.output, "seconds": round(elapsed, 2),
        "input_tokens": usage.input_tokens, "output_tokens": usage.output_tokens,
        "requests": usage.requests, "cost_usd": float(usage.cost) if usage.cost is not None else None, "tool_calls": calls,
    })
    return record, out.getvalue()


def run_search(query: str) -> tuple[dict, str]:
    """STEP 2 と同じ、検索だけの実行。"""
    from app.config import RAG_TOP_K
    from app.retrieval import search

    hits = search(query)
    lines = [f"[search] {query} / RAG_TOP_K = {RAG_TOP_K}"]
    for i, hit in enumerate(hits, 1):
        lines.append(f"{i}. 第{hit['lecture']}回 p.{hit['page']} {hit['title']} / distance={hit['distance']:.4f}")
        lines.append("   " + hit["content"].strip().replace("\n", " ")[:200])
    record = {"mode": "search", "question": query, "rag_top_k": RAG_TOP_K,
              "pages": [page_ref(hit) for hit in hits]}
    return record, "\n".join(lines) + "\n"


def run_phase(runs: list[tuple[str, str, str]]) -> None:
    done = load_results()
    for label, mode, question in runs:
        if label in done and "error" not in done[label]:
            print(f"[skip] {label}（記録済み）")
            continue
        print(f"\n{'=' * 70}\n[run] {label}\n{'=' * 70}")
        record, log = run_search(question) if mode == "search" else run_agent(mode, question)
        save_result(label, record, log)
        print(log)
        # 無料枠のレート制限（1分あたりの回数・トークン数）に配慮して間隔を空ける。
        time.sleep(60 if mode == "full" else 15)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--phase", choices=["before", "after"], help="内部用。通常は指定しない")
    args = parser.parse_args()
    from app.config import get_api_key
    get_api_key()  # 未設定なら、ここで手順を表示して終了する
    if args.phase:
        expected = BEFORE_K if args.phase == "before" else AFTER_K
        if current_top_k() != expected:
            raise SystemExit(f"RAG_TOP_K が {expected} ではありません。")
        run_phase(BEFORE_RUNS if args.phase == "before" else AFTER_RUNS)
        return

    # 設定はimport時に読まれるので、変更前・変更後を別プロセスで実行する。
    def phase(name: str) -> None:
        subprocess.run([sys.executable, "-m", "scripts.hw05_kiso", "--phase", name], cwd=ROOT, check=True)

    done = load_results()
    before_done = all(l in done and "error" not in done[l] for l, _, _ in BEFORE_RUNS if l != "ex_full")
    if current_top_k() == BEFORE_K:
        phase("before")
        set_top_k(BEFORE_K, AFTER_K)
        print(f"\n>>> app/config.py: RAG_TOP_K = {BEFORE_K} → {AFTER_K} に変更しました\n")
    elif current_top_k() != AFTER_K or not before_done:
        raise SystemExit(f"変更前の記録がそろっていません。RAG_TOP_K を {BEFORE_K} に戻してから実行してください。")
    phase("after")
    print(f"\n完了。記録は {LOG_DIR.relative_to(ROOT)}/ にあります。")


if __name__ == "__main__":
    main()
