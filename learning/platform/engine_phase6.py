"""Phase 6 learning engine helpers.

Generates lesson cards and quiz payloads from curriculum artifacts.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[2]
CURRICULUM_DIR = ROOT / "learning" / "curriculum"


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_lesson_packs() -> List[dict]:
    return _read_json(CURRICULUM_DIR / "phase6_lesson_packs.json")


def load_quiz_templates() -> List[dict]:
    return _read_json(CURRICULUM_DIR / "phase6_quiz_templates.json")


def load_vocab_index() -> Dict[str, dict]:
    return _read_json(CURRICULUM_DIR / "phase6_vocab_index.json")


def get_lesson_by_id(lesson_id: str) -> dict | None:
    for lesson in load_lesson_packs():
        if lesson.get("lesson_id") == lesson_id:
            return lesson
    return None


def get_quiz_for_lesson(lesson_id: str) -> dict | None:
    for quiz in load_quiz_templates():
        if quiz.get("lesson_id") == lesson_id:
            return quiz
    return None


def build_lesson_runtime_payload(lesson_id: str) -> dict | None:
    lesson = get_lesson_by_id(lesson_id)
    if not lesson:
        return None

    vocab = load_vocab_index()
    cards = []
    for word in lesson.get("target_words", []):
        key = "".join(ch.lower() if ch.isalnum() else "_" for ch in word).strip("_")
        item = vocab.get(key)
        if not item:
            continue
        cards.append(
            {
                "word": item["word"],
                "asset": item["asset"],
                "level": item["level"],
                "sublevel": item["sublevel"],
            }
        )

    return {
        "lesson_id": lesson_id,
        "title": lesson.get("lesson_goal"),
        "cards": cards,
        "quiz": get_quiz_for_lesson(lesson_id),
    }
