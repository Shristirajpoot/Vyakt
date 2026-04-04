#!/usr/bin/env python3
"""Generate Phase 7 and Phase 8 artifacts for gamification and personalization."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CURRICULUM_DIR = ROOT / "learning" / "curriculum"


def read_json(path: Path) -> dict | list:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict | list) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def build_phase7_runtime(phase3: dict, lesson_packs: list[dict]) -> dict:
    lessons_per_sublevel = {}
    for lesson in lesson_packs:
        key = lesson["sublevel"]
        lessons_per_sublevel[key] = lessons_per_sublevel.get(key, 0) + 1

    return {
        "phase": "Phase 7 - Gamification Runtime",
        "database": "mongodb",
        "runtime_rules": {
            "xp": phase3["xp_rules"],
            "hearts": phase3["hearts_system"],
            "streak": phase3["streak_rules"],
            "daily_quests": phase3["daily_quests"],
            "badges": phase3["badges"],
        },
        "reward_events": [
            {
                "event": "lesson_completed",
                "emit": ["xp_ledger", "daily_progress", "audit_events"],
                "required_payload": ["user_id", "lesson_id", "score_percent", "correct_answers"],
            },
            {
                "event": "sublevel_unlocked",
                "emit": ["progress", "audit_events"],
                "required_payload": ["user_id", "sublevel", "next_sublevel"],
            },
            {
                "event": "badge_unlocked",
                "emit": ["user_badges", "audit_events"],
                "required_payload": ["user_id", "badge_id", "reason"],
            },
        ],
        "leaderboard_runtime": {
            "windows": ["weekly", "all_time"],
            "refresh_policy": "recompute every 15 minutes or on-demand for top 100",
            "score_formula": phase3["leaderboard"]["rank_score_formula"],
        },
        "progression_map": {
            "sublevel_lesson_counts": lessons_per_sublevel,
            "minimum_completion_for_unlock": 0.80,
        },
    }


def build_phase8_personalization(phase2: dict, quiz_templates: list[dict]) -> dict:
    levels = phase2.get("levels", [])
    weak_skill_threshold = 0.65

    lesson_lookup = {
        quiz["lesson_id"]: {
            "level": quiz["level"],
            "sublevel": quiz["sublevel"],
            "question_count": len(quiz.get("questions", [])),
        }
        for quiz in quiz_templates
    }

    return {
        "phase": "Phase 8 - Personalization and Retention",
        "database": "mongodb",
        "personalization_rules": {
            "weak_skill_threshold": weak_skill_threshold,
            "repeat_missed_words_weight": 0.55,
            "recent_mistakes_boost": 0.30,
            "streak_preservation_boost": 0.15,
            "next_lesson_strategy": "prefer current sublevel; if mastery >= 85% then unlock next",
        },
        "retention_loops": {
            "daily_nudge": {
                "trigger_hours": [10, 18],
                "copy_template": "You are {streak_days} day streak away from your next badge.",
            },
            "weekly_summary": {
                "send_day": "Sunday",
                "fields": [
                    "lessons_completed",
                    "accuracy_percent",
                    "new_badges",
                    "xp_gained",
                    "top_3_improved_words",
                ],
            },
            "recovery_flow": {
                "trigger": "streak_missed_with_no_freeze",
                "offer": "complete one recovery lesson within 24h to restore streak",
            },
        },
        "adaptive_content": {
            "levels": len(levels),
            "lessons": lesson_lookup,
            "revision_queue_policy": "last 20 incorrect answers prioritized by recency and frequency",
        },
    }


def build_phase7_api_contracts() -> dict:
    return {
        "phase": "Phase 7 API Contracts",
        "base_path": "/api/v1",
        "endpoints": [
            {
                "method": "POST",
                "path": "/gamification/apply-lesson-result",
                "body": {
                    "user_id": "u123",
                    "lesson_id": "b1_foundations_lesson_01",
                    "score_percent": 84,
                    "correct_answers": 5,
                    "total_questions": 6,
                },
                "response": {
                    "xp_awarded": 77,
                    "hearts_left": 4,
                    "streak_days": 6,
                    "badges_unlocked": ["precision_pro"],
                    "sublevel_unlocked": True,
                },
            },
            {
                "method": "GET",
                "path": "/gamification/leaderboard/weekly",
                "response": {
                    "window": "weekly",
                    "items": [],
                },
            },
        ],
    }


def build_phase8_api_contracts() -> dict:
    return {
        "phase": "Phase 8 API Contracts",
        "base_path": "/api/v1",
        "endpoints": [
            {
                "method": "GET",
                "path": "/personalization/next-lesson",
                "query": {"user_id": "u123"},
                "response": {
                    "recommended_lesson_id": "b1_foundations_lesson_02",
                    "reason": "weak_words_overlap + streak_preservation",
                },
            },
            {
                "method": "GET",
                "path": "/personalization/revision-queue",
                "query": {"user_id": "u123"},
                "response": {
                    "words": ["Hello", "Where", "Thank"],
                },
            },
            {
                "method": "GET",
                "path": "/retention/weekly-summary",
                "query": {"user_id": "u123"},
                "response": {
                    "lessons_completed": 14,
                    "accuracy_percent": 82,
                    "xp_gained": 620,
                    "new_badges": ["week_warrior"],
                },
            },
        ],
    }


def write_readme() -> None:
    content = """# Phase 7 + Phase 8 Deliverables (MongoDB)

## Files
- phase7_gamification_runtime.json
- phase7_api_contracts.json
- phase8_personalization_retention.json
- phase8_api_contracts.json

## What you get
1. Runtime gamification event model (XP, hearts, streak, badges, leaderboard).
2. Personalization and retention rules for recommendation and re-engagement.
3. API contract docs for implementing endpoints quickly.

## Next
- Wire learning/platform/api_phase7_phase8.py into Flask app.
- Replace demo payloads with MongoDB aggregation reads.
"""
    (CURRICULUM_DIR / "README_PHASE7_PHASE8.md").write_text(content, encoding="utf-8")


def main() -> None:
    phase2 = read_json(CURRICULUM_DIR / "phase2_levels.json")
    phase3 = read_json(CURRICULUM_DIR / "phase3_gamification.json")
    lesson_packs = read_json(CURRICULUM_DIR / "phase6_lesson_packs.json")
    quiz_templates = read_json(CURRICULUM_DIR / "phase6_quiz_templates.json")

    write_json(CURRICULUM_DIR / "phase7_gamification_runtime.json", build_phase7_runtime(phase3, lesson_packs))
    write_json(CURRICULUM_DIR / "phase7_api_contracts.json", build_phase7_api_contracts())
    write_json(
        CURRICULUM_DIR / "phase8_personalization_retention.json",
        build_phase8_personalization(phase2, quiz_templates),
    )
    write_json(CURRICULUM_DIR / "phase8_api_contracts.json", build_phase8_api_contracts())
    write_readme()

    print("Generated Phase 7 + Phase 8 artifacts in learning/curriculum")


if __name__ == "__main__":
    main()
