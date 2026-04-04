#!/usr/bin/env python3
"""Generate Phase 5 and Phase 6 artifacts for MongoDB-backed learning platform."""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[1]
CURRICULUM_DIR = ROOT / "learning" / "curriculum"
RNG = random.Random(42)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_key(name: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in name).strip("_")


def build_vocab_index(levels: List[dict]) -> Dict[str, dict]:
    index: Dict[str, dict] = {}
    for level in levels:
        level_name = level["name"]
        for sub in level.get("sublevels", []):
            for word in sub.get("words", []):
                key = normalize_key(word)
                index[key] = {
                    "word": word,
                    "asset": f"static/assets/{word}.mp4",
                    "level": level_name,
                    "sublevel": sub["name"],
                }
    return index


def build_phase5(levels: List[dict], phase3: dict) -> dict:
    return {
        "phase": "Phase 5 - Backend Data Model and APIs",
        "database": "mongodb",
        "service": {
            "name": "learning_service",
            "version": "v1",
            "base_path": "/api/v1",
        },
        "collections": {
            "lesson_sessions": {
                "fields": ["_id", "user_id", "lesson_id", "sublevel", "status", "started_at", "finished_at"],
                "indexes": ["user_id_started_at_desc", "lesson_id"],
            },
            "question_attempts": {
                "fields": ["_id", "session_id", "question_id", "selected", "correct", "response_ms", "created_at"],
                "indexes": ["session_id", "created_at_desc"],
            },
            "xp_ledger": {
                "fields": ["_id", "user_id", "reason", "xp_delta", "metadata", "created_at"],
                "indexes": ["user_id_created_at_desc", "reason"],
            },
            "daily_progress": {
                "fields": ["_id", "user_id", "date", "lessons_completed", "correct_answers", "xp_gained"],
                "indexes": ["user_id_date_unique"],
            },
        },
        "api_contracts": [
            {
                "name": "get_home_progress",
                "method": "GET",
                "path": "/api/v1/progress/home",
                "response": {
                    "current_level": "beginner",
                    "current_sublevel": "B1 Foundations",
                    "xp": 220,
                    "hearts": phase3["hearts_system"]["max_hearts"],
                    "streak_days": 5,
                    "next_lesson_id": "b1_foundations_lesson_01",
                },
            },
            {
                "name": "start_lesson",
                "method": "POST",
                "path": "/api/v1/lesson/start",
                "body": {"sublevel": "B1 Foundations", "lesson_id": "b1_foundations_lesson_01"},
                "response": {"session_id": "sess_xxx", "xp_grant": phase3["xp_rules"]["lesson_start"]},
            },
            {
                "name": "submit_answer",
                "method": "POST",
                "path": "/api/v1/lesson/answer",
                "body": {"session_id": "sess_xxx", "question_id": "q01", "selected": "Hello"},
                "response": {
                    "correct": True,
                    "xp_delta": phase3["xp_rules"]["correct_answer"],
                    "hearts_left": 4,
                },
            },
            {
                "name": "finish_lesson",
                "method": "POST",
                "path": "/api/v1/lesson/finish",
                "body": {"session_id": "sess_xxx"},
                "response": {
                    "score_percent": 84,
                    "badges_unlocked": ["first_sign"],
                    "sublevel_unlocked": True,
                },
            },
            {
                "name": "get_daily_quests",
                "method": "GET",
                "path": "/api/v1/quests/today",
                "response": {"quests": phase3["daily_quests"]},
            },
            {
                "name": "get_weekly_leaderboard",
                "method": "GET",
                "path": "/api/v1/leaderboard/weekly",
                "response": {"window": "weekly", "items": []},
            },
        ],
        "state_machine": {
            "lesson_session_states": ["started", "in_progress", "completed", "abandoned"],
            "transitions": [
                "started -> in_progress on first answer",
                "in_progress -> completed on finish endpoint",
                "in_progress -> abandoned on inactivity timeout",
            ],
        },
    }


def build_lesson_packs(levels: List[dict], cards_per_lesson: int = 8) -> list[dict]:
    packs = []
    for level in levels:
        for sub in level.get("sublevels", []):
            words = list(sub.get("words", []))
            lesson_idx = 1
            for i in range(0, len(words), cards_per_lesson):
                chunk = words[i : i + cards_per_lesson]
                sub_id = normalize_key(sub["name"])
                lesson_id = f"{sub_id}_lesson_{lesson_idx:02d}"
                packs.append(
                    {
                        "lesson_id": lesson_id,
                        "level": level["name"],
                        "sublevel": sub["name"],
                        "target_words": chunk,
                        "lesson_goal": f"Learn {len(chunk)} signs in {sub['name']}",
                        "unlock_rule": "Previous lesson score >= 70%",
                    }
                )
                lesson_idx += 1
    return packs


def build_quiz_templates(lesson_packs: List[dict], vocab_index: Dict[str, dict], per_lesson: int = 6) -> list[dict]:
    templates = []

    words_by_level: Dict[str, List[str]] = {}
    for item in vocab_index.values():
        words_by_level.setdefault(item["level"], []).append(item["word"])

    for lesson in lesson_packs:
        level = lesson["level"]
        lesson_words = lesson["target_words"]
        distractor_pool = [w for w in words_by_level.get(level, []) if w not in lesson_words]
        if len(distractor_pool) < 3:
            distractor_pool = [v["word"] for v in vocab_index.values() if v["word"] not in lesson_words]

        question_count = min(per_lesson, len(lesson_words))
        questions = []

        for q_idx, correct_word in enumerate(lesson_words[:question_count], start=1):
            options = {correct_word}
            while len(options) < 4 and distractor_pool:
                options.add(RNG.choice(distractor_pool))
            options_list = list(options)
            RNG.shuffle(options_list)

            questions.append(
                {
                    "question_id": f"{lesson['lesson_id']}_q{q_idx:02d}",
                    "type": "identify_sign_from_video",
                    "prompt": "Watch the sign and choose the correct word.",
                    "asset": f"static/assets/{correct_word}.mp4",
                    "options": options_list,
                    "correct": correct_word,
                    "xp_on_correct": 10,
                }
            )

        templates.append(
            {
                "lesson_id": lesson["lesson_id"],
                "level": lesson["level"],
                "sublevel": lesson["sublevel"],
                "questions": questions,
            }
        )

    return templates


def write_json(path: Path, payload: dict | list) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_readme(lesson_packs: list[dict], quiz_templates: list[dict]) -> None:
    total_questions = sum(len(t.get("questions", [])) for t in quiz_templates)

    content = f"""# Phase 5 + Phase 6 Deliverables (MongoDB)

## Files
- phase5_backend_contracts.json
- phase6_lesson_packs.json
- phase6_quiz_templates.json
- phase6_vocab_index.json

## Snapshot
- Total generated lessons: {len(lesson_packs)}
- Total generated quiz templates: {len(quiz_templates)}
- Total generated questions: {total_questions}

## Phase 5 scope
- MongoDB collections for sessions, attempts, xp ledger, daily progress.
- API contracts for progress, lesson lifecycle, quests, leaderboard.

## Phase 6 scope
- Auto-generated lessons from Phase 2 sublevels.
- Auto-generated quiz question templates with distractors.
- Vocab index with asset mapping for runtime APIs.
"""
    (CURRICULUM_DIR / "README_PHASE5_PHASE6.md").write_text(content, encoding="utf-8")


def main() -> None:
    phase2 = read_json(CURRICULUM_DIR / "phase2_levels.json")
    phase3 = read_json(CURRICULUM_DIR / "phase3_gamification.json")

    levels = phase2.get("levels", [])
    vocab_index = build_vocab_index(levels)
    phase5 = build_phase5(levels, phase3)
    lesson_packs = build_lesson_packs(levels, cards_per_lesson=8)
    quiz_templates = build_quiz_templates(lesson_packs, vocab_index, per_lesson=6)

    write_json(CURRICULUM_DIR / "phase5_backend_contracts.json", phase5)
    write_json(CURRICULUM_DIR / "phase6_lesson_packs.json", lesson_packs)
    write_json(CURRICULUM_DIR / "phase6_quiz_templates.json", quiz_templates)
    write_json(CURRICULUM_DIR / "phase6_vocab_index.json", vocab_index)
    write_readme(lesson_packs, quiz_templates)

    print("Generated Phase 5 + Phase 6 artifacts in learning/curriculum")


if __name__ == "__main__":
    main()
