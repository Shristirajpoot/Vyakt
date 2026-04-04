"""Phase 7 + 8 API scaffold.

Standalone blueprint that can be registered in app.py when ready.
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from learning.platform.service_phase7_8 import (
    LessonResult,
    build_revision_queue,
    calculate_xp_award,
    evaluate_badges,
    hearts_delta,
    recommend_next_lesson,
    weekly_summary_payload,
)

phase7_8_api = Blueprint("phase7_8_api", __name__, url_prefix="/api/v1")


@phase7_8_api.post("/gamification/apply-lesson-result")
def apply_lesson_result():
    payload = request.get_json(silent=True) or {}

    required = [
        "user_id",
        "lesson_id",
        "score_percent",
        "correct_answers",
        "total_questions",
        "streak_days",
    ]
    missing = [k for k in required if k not in payload]
    if missing:
        return jsonify({"error": f"Missing fields: {', '.join(missing)}"}), 400

    result = LessonResult(
        user_id=str(payload["user_id"]),
        lesson_id=str(payload["lesson_id"]),
        score_percent=int(payload["score_percent"]),
        correct_answers=int(payload["correct_answers"]),
        total_questions=int(payload["total_questions"]),
        streak_days=int(payload["streak_days"]),
    )

    state = {
        "lessons_completed": int(payload.get("lessons_completed", 0)),
    }

    xp_awarded = calculate_xp_award(result)
    badges_unlocked = evaluate_badges(state, result)
    hearts_change = hearts_delta(result.score_percent)

    return jsonify(
        {
            "xp_awarded": xp_awarded,
            "hearts_delta": hearts_change,
            "badges_unlocked": badges_unlocked,
            "sublevel_unlocked": result.score_percent >= 80,
        }
    )


@phase7_8_api.get("/gamification/leaderboard/weekly")
def leaderboard_weekly():
    # Placeholder output; replace with Mongo aggregation.
    return jsonify({"window": "weekly", "items": []})


@phase7_8_api.get("/personalization/next-lesson")
def next_lesson():
    current = request.args.get("current_lesson_id", "")
    available = request.args.getlist("available")
    weak = request.args.getlist("weak")
    streak_at_risk = request.args.get("streak_at_risk", "false").lower() == "true"

    if not available:
        return jsonify({"error": "available query values are required"}), 400

    recommended = recommend_next_lesson(current, available, weak, streak_at_risk)
    reason = "weak_lesson_priority" if weak else "sequential_progression"

    return jsonify({"recommended_lesson_id": recommended, "reason": reason})


@phase7_8_api.get("/personalization/revision-queue")
def revision_queue():
    incorrect_words = request.args.getlist("word")
    queue = build_revision_queue(incorrect_words)
    return jsonify({"words": queue})


@phase7_8_api.get("/retention/weekly-summary")
def weekly_summary():
    user_id = request.args.get("user_id", "demo_user")
    lessons_completed = int(request.args.get("lessons_completed", "0"))
    accuracy_percent = int(request.args.get("accuracy_percent", "0"))
    xp_gained = int(request.args.get("xp_gained", "0"))
    new_badges = request.args.getlist("badge")

    return jsonify(
        weekly_summary_payload(
            user_id=user_id,
            lessons_completed=lessons_completed,
            accuracy_percent=accuracy_percent,
            xp_gained=xp_gained,
            new_badges=new_badges,
        )
    )
