#!/usr/bin/env python3
"""Generate Phase 3 (gamification economy) and Phase 4 (UI blueprint) artifacts.

MongoDB is treated as the canonical database for the learning platform.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CURRICULUM_DIR = ROOT / "learning" / "curriculum"


def load_phase2_levels() -> list[dict]:
    path = CURRICULUM_DIR / "phase2_levels.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("levels", [])


def build_phase3(levels: list[dict]) -> dict:
    sublevel_count = sum(len(level.get("sublevels", [])) for level in levels)

    return {
        "phase": "Phase 3 - Gamification Economy",
        "database": "mongodb",
        "xp_rules": {
            "lesson_start": 2,
            "correct_answer": 10,
            "perfect_lesson_bonus": 25,
            "sublevel_complete": 80,
            "level_complete": 200,
            "daily_goal_complete": 40,
            "streak_bonus_multiplier": {
                "1_to_6_days": 1.0,
                "7_to_29_days": 1.15,
                "30_plus_days": 1.35,
            },
        },
        "hearts_system": {
            "max_hearts": 5,
            "heart_loss_on_wrong": 1,
            "refill": {
                "full_refill_every_hours": 12,
                "practice_refill_per_session": 1,
            },
        },
        "streak_rules": {
            "daily_activity_min_lessons": 1,
            "timezone_source": "user_profile.timezone",
            "freeze_tokens": {
                "max_tokens": 2,
                "grant_every_days": 7,
                "consume_on_miss": 1,
            },
        },
        "badges": [
            {"id": "first_sign", "name": "First Sign", "trigger": "Complete first lesson"},
            {"id": "week_warrior", "name": "Week Warrior", "trigger": "7-day streak"},
            {"id": "precision_pro", "name": "Precision Pro", "trigger": "5 perfect lessons"},
            {"id": "consistent_learner", "name": "Consistent Learner", "trigger": "30 lessons completed"},
            {"id": "level_climber", "name": "Level Climber", "trigger": "Complete any level"},
            {"id": "advanced_runner", "name": "Advanced Runner", "trigger": "Complete advanced level"},
        ],
        "daily_quests": [
            {"id": "dq_1", "title": "Complete 2 lessons", "reward_xp": 30},
            {"id": "dq_2", "title": "Maintain streak today", "reward_xp": 20},
            {"id": "dq_3", "title": "Get 8 correct answers", "reward_xp": 35},
        ],
        "unlock_logic": {
            "sublevel_unlock": "score_percent >= 80 and hearts > 0",
            "level_unlock": "average_sublevel_score >= 75 and previous_level_completed = true",
            "total_levels": len(levels),
            "total_sublevels": sublevel_count,
        },
        "leaderboard": {
            "windows": ["weekly", "all_time"],
            "rank_score_formula": "(total_xp * 0.7) + (streak_days * 8) + (perfect_lessons * 5)",
            "anti_cheat": {
                "max_lesson_submissions_per_minute": 8,
                "duplicate_attempt_hash_block": True,
            },
        },
    }


def build_phase4(levels: list[dict]) -> dict:
    unit_count = sum(len(level.get("sublevels", [])) for level in levels)

    return {
        "phase": "Phase 4 - UI and UX Blueprint",
        "ui_direction": "playful_learning_path_inspired",
        "database": "mongodb",
        "screen_map": [
            {
                "id": "home_path",
                "title": "Learning Path Home",
                "goal": "Show progression nodes for all sublevels",
                "widgets": [
                    "streak_chip",
                    "xp_meter",
                    "heart_meter",
                    "unit_path_nodes",
                    "daily_quests_card",
                ],
                "api_dependencies": [
                    "GET /api/v1/progress/home",
                    "GET /api/v1/quests/today",
                ],
            },
            {
                "id": "lesson_player",
                "title": "Lesson Player",
                "goal": "Teach signs in bite-size cards and interactive checks",
                "widgets": [
                    "sign_video_panel",
                    "answer_options",
                    "confidence_feedback",
                    "hearts_status",
                    "continue_button",
                ],
                "api_dependencies": [
                    "POST /api/v1/lesson/start",
                    "POST /api/v1/lesson/answer",
                    "POST /api/v1/lesson/finish",
                ],
            },
            {
                "id": "reward_modal",
                "title": "Reward and Celebration",
                "goal": "Celebrate XP gain, badge unlock, and streak progress",
                "widgets": [
                    "xp_counter_animation",
                    "badge_unlock_tile",
                    "streak_fire_meter",
                ],
                "api_dependencies": [
                    "GET /api/v1/rewards/last",
                ],
            },
            {
                "id": "profile_stats",
                "title": "Profile and Stats",
                "goal": "Show history, badges, and level completion",
                "widgets": [
                    "badge_grid",
                    "accuracy_chart",
                    "lesson_history",
                    "current_league",
                ],
                "api_dependencies": [
                    "GET /api/v1/profile/stats",
                    "GET /api/v1/leaderboard/weekly",
                ],
            },
            {
                "id": "shop_screen",
                "title": "Reward Shop",
                "goal": "Spend earned gems on streak freeze and cosmetic items",
                "widgets": [
                    "gem_balance",
                    "shop_item_cards",
                    "purchase_action",
                ],
                "api_dependencies": [
                    "GET /api/v1/shop/items",
                    "POST /api/v1/shop/purchase",
                ],
            },
        ],
        "layout_system": {
            "mobile_first": True,
            "breakpoints": {
                "sm": 480,
                "md": 768,
                "lg": 1024,
            },
            "navigation": {
                "mobile": "bottom_tab_nav",
                "desktop": "left_rail",
            },
        },
        "motion_specs": {
            "micro_interactions": [
                "lesson_card_flip_220ms",
                "xp_counter_pop_300ms",
                "badge_unlock_sparkle_900ms",
            ],
            "reduced_motion_support": True,
        },
        "content_density": {
            "levels": len(levels),
            "path_nodes": unit_count,
            "recommended_cards_per_lesson": 8,
            "recommended_quiz_questions": 6,
        },
    }


def build_mongodb_schema(levels: list[dict]) -> dict:
    return {
        "database": "Vyakt_learning",
        "collections": {
            "users": {
                "description": "Auth profile and user role",
                "required_fields": ["_id", "email", "username", "role", "created_at"],
                "indexes": ["email_unique", "role"],
            },
            "learning_paths": {
                "description": "Static phase2 structure for levels and sublevels",
                "required_fields": ["_id", "level", "sublevel", "word_ids", "unlock_rule"],
                "indexes": ["level", "sublevel"],
            },
            "vocabulary": {
                "description": "All dataset words and metadata",
                "required_fields": ["_id", "word", "asset_file", "difficulty_score", "level"],
                "indexes": ["word_unique", "level", "sublevel"],
            },
            "lesson_attempts": {
                "description": "Per-lesson answer data",
                "required_fields": ["_id", "user_id", "sublevel", "score_percent", "answers", "created_at"],
                "indexes": ["user_id_created_at", "sublevel"],
            },
            "progress": {
                "description": "Current user progression snapshot",
                "required_fields": ["_id", "user_id", "current_level", "current_sublevel", "xp", "hearts", "streak_days"],
                "indexes": ["user_id_unique", "xp_desc"],
            },
            "badges": {
                "description": "Badge catalog",
                "required_fields": ["_id", "badge_id", "name", "trigger"],
                "indexes": ["badge_id_unique"],
            },
            "user_badges": {
                "description": "Awarded badges",
                "required_fields": ["_id", "user_id", "badge_id", "awarded_at"],
                "indexes": ["user_id", "badge_id"],
            },
            "quests": {
                "description": "Daily and weekly quests",
                "required_fields": ["_id", "quest_id", "title", "reward_xp", "window"],
                "indexes": ["quest_id_unique", "window"],
            },
            "leaderboards": {
                "description": "Cached ranking board documents",
                "required_fields": ["_id", "window", "user_id", "rank_score", "updated_at"],
                "indexes": ["window_rank_score_desc", "user_id"],
            },
            "audit_events": {
                "description": "Policy and gameplay audit trail",
                "required_fields": ["_id", "user_id", "event_type", "status", "reason", "timestamp"],
                "indexes": ["timestamp_desc", "user_id", "event_type"],
            },
        },
        "notes": {
            "source_levels_count": len(levels),
            "write_strategy": "append-only for attempts and audit_events",
            "consistency": "single-document updates for progress, transaction for reward + progress when needed",
        },
    }


def build_mongosh_init() -> str:
    return """use Vyakt_learning;

db.users.createIndex({ email: 1 }, { unique: true, name: 'email_unique' });
db.users.createIndex({ role: 1 }, { name: 'role_idx' });

db.learning_paths.createIndex({ level: 1, sublevel: 1 }, { name: 'level_sublevel_idx' });

db.vocabulary.createIndex({ word: 1 }, { unique: true, name: 'word_unique' });
db.vocabulary.createIndex({ level: 1, sublevel: 1 }, { name: 'vocab_level_idx' });

db.lesson_attempts.createIndex({ user_id: 1, created_at: -1 }, { name: 'user_attempts_idx' });
db.lesson_attempts.createIndex({ sublevel: 1 }, { name: 'attempt_sublevel_idx' });

db.progress.createIndex({ user_id: 1 }, { unique: true, name: 'progress_user_unique' });
db.progress.createIndex({ xp: -1 }, { name: 'progress_xp_desc' });

db.badges.createIndex({ badge_id: 1 }, { unique: true, name: 'badge_id_unique' });
db.user_badges.createIndex({ user_id: 1, badge_id: 1 }, { name: 'user_badges_idx' });

db.quests.createIndex({ quest_id: 1 }, { unique: true, name: 'quest_id_unique' });
db.quests.createIndex({ window: 1 }, { name: 'quest_window_idx' });

db.leaderboards.createIndex({ window: 1, rank_score: -1 }, { name: 'window_rank_score_desc' });
db.leaderboards.createIndex({ user_id: 1 }, { name: 'leaderboard_user_idx' });

db.audit_events.createIndex({ timestamp: -1 }, { name: 'audit_timestamp_desc' });
db.audit_events.createIndex({ user_id: 1, event_type: 1 }, { name: 'audit_user_event_idx' });
"""


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_readme() -> None:
    readme = """# Phase 3 + Phase 4 Deliverables (MongoDB)

## Generated Files
- phase3_gamification.json
- phase4_ui_blueprint.json
- mongodb_schema.json
- mongodb_init.js

## What this gives you
1. XP, streak, hearts, badge, quest, and leaderboard economy config.
2. Screen-by-screen UI blueprint for implementation.
3. MongoDB collections and index plan for production-ready storage.
4. Mongosh script to initialize indexes quickly.

## Next implementation steps
1. Create Flask APIs under /api/v1 based on phase4_ui_blueprint.json dependencies.
2. Connect MongoDB using pymongo or motor.
3. Store lesson attempts in lesson_attempts and live progress in progress.
4. Use audit_events for policy and gameplay evidence.
"""
    (CURRICULUM_DIR / "README_PHASE3_PHASE4.md").write_text(readme, encoding="utf-8")


def main() -> None:
    levels = load_phase2_levels()

    write_json(CURRICULUM_DIR / "phase3_gamification.json", build_phase3(levels))
    write_json(CURRICULUM_DIR / "phase4_ui_blueprint.json", build_phase4(levels))
    write_json(CURRICULUM_DIR / "mongodb_schema.json", build_mongodb_schema(levels))
    (CURRICULUM_DIR / "mongodb_init.js").write_text(build_mongosh_init(), encoding="utf-8")
    write_readme()

    print("Generated Phase 3 + Phase 4 MongoDB artifacts in learning/curriculum")


if __name__ == "__main__":
    main()
