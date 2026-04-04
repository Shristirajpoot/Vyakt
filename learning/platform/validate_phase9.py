"""Lightweight validation checks for Phase 9 readiness.

Usage:
    python3 learning/platform/validate_phase9.py
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CURRICULUM_DIR = ROOT / "learning" / "curriculum"

REQUIRED_FILES = [
    "phase5_backend_contracts.json",
    "phase6_lesson_packs.json",
    "phase6_quiz_templates.json",
    "phase7_gamification_runtime.json",
    "phase8_personalization_retention.json",
    "phase9_qa_analytics.json",
    "phase10_launch_checklist.json",
]


def read_json(name: str):
    path = CURRICULUM_DIR / name
    return json.loads(path.read_text(encoding="utf-8"))


def assert_required_files():
    missing = [name for name in REQUIRED_FILES if not (CURRICULUM_DIR / name).exists()]
    if missing:
        raise RuntimeError(f"Missing required files: {', '.join(missing)}")


def validate_lesson_quiz_alignment():
    lessons = read_json("phase6_lesson_packs.json")
    quizzes = read_json("phase6_quiz_templates.json")

    lesson_ids = {item["lesson_id"] for item in lessons}
    quiz_ids = {item["lesson_id"] for item in quizzes}

    if lesson_ids != quiz_ids:
        missing_quiz = sorted(lesson_ids - quiz_ids)
        missing_lesson = sorted(quiz_ids - lesson_ids)
        raise RuntimeError(
            "Lesson/quiz mismatch: "
            f"missing_quiz={missing_quiz[:5]}, missing_lesson={missing_lesson[:5]}"
        )


def validate_phase9_kpis():
    phase9 = read_json("phase9_qa_analytics.json")
    kpis = phase9.get("kpis", {})
    required = [
        "d1_retention_target",
        "lesson_completion_target",
        "avg_accuracy_target",
    ]
    missing = [k for k in required if k not in kpis]
    if missing:
        raise RuntimeError(f"Phase 9 KPI keys missing: {', '.join(missing)}")


def main():
    assert_required_files()
    validate_lesson_quiz_alignment()
    validate_phase9_kpis()
    print("Phase 9 validation passed")


if __name__ == "__main__":
    main()
