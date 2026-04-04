#!/usr/bin/env python3
"""Generate Phase 9 and Phase 10 artifacts for QA, analytics, demo, and launch."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CURRICULUM_DIR = ROOT / "learning" / "curriculum"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload):
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def build_phase9_qa_analytics(phase3: dict, phase5: dict, phase8: dict):
    return {
        "phase": "Phase 9 - QA, Analytics, and Demo Story",
        "database": "mongodb",
        "qa_matrix": {
            "gamification_tests": [
                "xp_award_correct_answer",
                "perfect_lesson_bonus",
                "streak_increment_same_day_guard",
                "streak_freeze_consumption",
                "badge_unlock_thresholds",
            ],
            "progression_tests": [
                "sublevel_unlock_at_80_percent",
                "level_unlock_at_75_percent_average",
                "hearts_block_when_zero",
            ],
            "api_tests": [endpoint["name"] for endpoint in phase5.get("api_contracts", [])],
            "personalization_tests": [
                "next_lesson_prefers_weak_skills",
                "revision_queue_recency_priority",
                "weekly_summary_fields_complete",
            ],
        },
        "analytics_events": [
            {
                "event": "lesson_started",
                "collection": "audit_events",
                "properties": ["user_id", "lesson_id", "sublevel", "timestamp"],
            },
            {
                "event": "lesson_completed",
                "collection": "lesson_attempts",
                "properties": ["user_id", "lesson_id", "score_percent", "correct_answers", "xp_awarded"],
            },
            {
                "event": "badge_unlocked",
                "collection": "user_badges",
                "properties": ["user_id", "badge_id", "awarded_at"],
            },
            {
                "event": "recommendation_served",
                "collection": "audit_events",
                "properties": ["user_id", "recommended_lesson_id", "reason", "timestamp"],
            },
        ],
        "kpis": {
            "d1_retention_target": ">= 45%",
            "lesson_completion_target": ">= 70%",
            "avg_accuracy_target": ">= 75%",
            "weekly_active_learners_target": ">= 30 for demo cohort",
            "streak_7day_target": ">= 25% users",
        },
        "dashboards": {
            "product": [
                "daily_active_learners",
                "lesson_completion_rate",
                "median_score_percent",
                "streak_distribution",
            ],
            "quality": [
                "api_error_rate",
                "invalid_payload_rate",
                "quiz_render_latency_ms",
            ],
            "learning_outcomes": [
                "top_improved_words",
                "most_missed_words",
                "level_completion_funnel",
            ],
        },
        "demo_storyboard": [
            "User signs in and resumes streak",
            "Completes one lesson and earns XP",
            "Unlocks badge and next sublevel",
            "Personalized next-lesson recommendation appears",
            "Leaderboard and weekly summary shown",
        ],
        "config_references": {
            "xp_rules": phase3.get("xp_rules", {}),
            "personalization": phase8.get("personalization_rules", {}),
        },
    }


def build_phase9_test_plan():
    return {
        "phase": "Phase 9 Test Plan",
        "suites": [
            {
                "suite": "unit",
                "target": "service_phase7_8.py",
                "cases": [
                    "calculate_xp_award",
                    "hearts_delta",
                    "evaluate_badges",
                    "recommend_next_lesson",
                    "build_revision_queue",
                ],
            },
            {
                "suite": "contract",
                "target": "phase5/phase7/phase8 endpoints",
                "cases": [
                    "required_fields_validation",
                    "response_shape_validation",
                    "error_status_codes",
                ],
            },
            {
                "suite": "integration",
                "target": "MongoDB collections",
                "cases": [
                    "xp_ledger_written_on_lesson_complete",
                    "progress_updated_atomically",
                    "leaderboard_refresh_job",
                ],
            },
            {
                "suite": "e2e",
                "target": "lesson flow",
                "cases": [
                    "start_to_finish_lesson",
                    "sublevel_unlock_flow",
                    "streak_recovery_flow",
                ],
            },
        ],
    }


def build_phase10_launch(phase4: dict):
    return {
        "phase": "Phase 10 - Hackathon Polish and Launch",
        "launch_readiness": {
            "accessibility": [
                "keyboard_navigable_lessons",
                "visible_focus_states",
                "captions_for_all_videos",
                "reduced_motion_mode",
                "contrast_ratio_aa_or_better",
            ],
            "performance": [
                "home_load_under_2s",
                "lesson_transition_under_300ms",
                "quiz_submit_under_200ms",
            ],
            "reliability": [
                "graceful_fallback_if_asset_missing",
                "idempotent_lesson_finish",
                "retry_on_temporary_db_failures",
            ],
            "security": [
                "input_validation_on_all_api_routes",
                "role_checks_for_admin_actions",
                "pii_safe_logging_enabled",
            ],
        },
        "judge_demo_pack": {
            "demo_duration_minutes": 5,
            "must_show": [
                "lesson completion with XP gain",
                "badge unlock animation",
                "streak increment",
                "personalized next lesson",
                "leaderboard update",
            ],
            "backup_flows": [
                "offline dataset-only mode",
                "pre-seeded demo account",
            ],
        },
        "pitch_variants": {
            "30_sec": "We built a gamified sign-language learning platform with adaptive progression, streak-based retention, and policy-ready auditability.",
            "2_min": "The platform converts your curated sign dataset into progressive lessons and quizzes. Learners earn XP, maintain streaks, unlock badges, and receive personalized recommendations. MongoDB powers event-driven progress tracking and leaderboard analytics.",
        },
        "ui_polish_targets": {
            "screen_count": len(phase4.get("screen_map", [])),
            "motion": phase4.get("motion_specs", {}),
            "mobile_first": phase4.get("layout_system", {}).get("mobile_first", True),
        },
    }


def build_phase10_runbook():
    return {
        "phase": "Phase 10 Demo Runbook",
        "t_minus_60": [
            "seed demo user and progress",
            "verify MongoDB connectivity",
            "warm up lesson assets",
        ],
        "t_minus_15": [
            "open home, lesson, profile, leaderboard tabs",
            "reset browser cache",
            "verify backup internet option",
        ],
        "live_demo": [
            "show current streak and daily quest",
            "start lesson and answer questions",
            "finish lesson and show rewards",
            "show recommendation engine",
            "show leaderboard and weekly summary",
        ],
        "if_failure": [
            "switch to pre-recorded fallback video",
            "load pre-seeded analytics snapshot",
            "continue with architecture walkthrough",
        ],
    }


def write_readme():
    text = """# Phase 9 + Phase 10 Deliverables

## Files
- phase9_qa_analytics.json
- phase9_test_plan.json
- phase10_launch_checklist.json
- phase10_demo_runbook.json

## What you get
1. QA matrix and analytics event schema.
2. Test plan for unit, contract, integration, and e2e coverage.
3. Launch checklist for accessibility, performance, reliability, and security.
4. Judge-ready demo runbook and pitch snippets.
"""
    (CURRICULUM_DIR / "README_PHASE9_PHASE10.md").write_text(text, encoding="utf-8")


def main():
    phase3 = read_json(CURRICULUM_DIR / "phase3_gamification.json")
    phase4 = read_json(CURRICULUM_DIR / "phase4_ui_blueprint.json")
    phase5 = read_json(CURRICULUM_DIR / "phase5_backend_contracts.json")
    phase8 = read_json(CURRICULUM_DIR / "phase8_personalization_retention.json")

    write_json(CURRICULUM_DIR / "phase9_qa_analytics.json", build_phase9_qa_analytics(phase3, phase5, phase8))
    write_json(CURRICULUM_DIR / "phase9_test_plan.json", build_phase9_test_plan())
    write_json(CURRICULUM_DIR / "phase10_launch_checklist.json", build_phase10_launch(phase4))
    write_json(CURRICULUM_DIR / "phase10_demo_runbook.json", build_phase10_runbook())
    write_readme()

    print("Generated Phase 9 + Phase 10 artifacts in learning/curriculum")


if __name__ == "__main__":
    main()
