"""第3回 演習・宿題（make_quiz と save_learning_log）のテスト。LLM も API キーも使わない。"""

import json

import pytest
from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart, ToolReturnPart
from pydantic_ai.models.function import FunctionModel

from app import tools
from app.agent import agent, run_with_approval


def test_make_quiz_returns_question_and_answer_for_lecture2():
    quiz = json.loads(tools.make_quiz(2))
    lec2_terms = {e["term"] for e in tools.load_glossary() if e["lecture"] == 2}
    term = quiz["question"].split("「")[1].split("」")[0]
    assert term in lec2_terms
    assert quiz["answer"]


def test_make_quiz_handles_missing_lecture():
    assert "ありません" in tools.make_quiz(0)


@pytest.fixture
def log_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(tools, "LOG_DIR", tmp_path / "learning_log")
    return tmp_path / "learning_log"


def _save_then_answer(messages, info):
    """1回目は save_learning_log を呼び、ツールの結果が返ってきたら文章で答える偽モデル。"""
    last = messages[-1].parts
    returned = [p for p in last if isinstance(p, ToolReturnPart)]
    if returned:
        return ModelResponse(parts=[TextPart(f"結果: {returned[0].content}")])
    return ModelResponse(parts=[ToolCallPart(
        "save_learning_log", {"title": "第3回 エージェント", "content": "- ループ＋ツール"})])


@pytest.mark.parametrize("approved", [True, False])
def test_save_learning_log_waits_for_approval(log_dir, approved):
    asked = []

    def approve(tool_name, args):
        asked.append(tool_name)
        return approved

    result = run_with_approval(agent, "今日の学びを保存して", FunctionModel(_save_then_answer), approve=approve)

    assert asked == ["save_learning_log"]  # 実行前に1回だけ確認された
    files = list(log_dir.glob("*.md")) if log_dir.exists() else []
    if approved:
        assert len(files) == 1 and "ループ＋ツール" in files[0].read_text(encoding="utf-8")
        assert "保存しました" in result.output
    else:
        assert files == []
        assert "拒否" in result.output
