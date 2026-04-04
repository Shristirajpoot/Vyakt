"""Phase 5 API scaffold for MongoDB-backed learning service.

This module is intentionally standalone and not auto-wired to app.py yet.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from flask import Blueprint, jsonify, request
from pymongo import MongoClient

learning_api = Blueprint("learning_api", __name__, url_prefix="/api/v1")


class LearningRepository:
    def __init__(self, mongo_uri: str, db_name: str = "Vyakt_learning") -> None:
        self.client = MongoClient(mongo_uri)
        self.db = self.client[db_name]

    def get_progress(self, user_id: str) -> Dict[str, Any] | None:
        return self.db.progress.find_one({"user_id": user_id}, {"_id": 0})

    def create_session(self, payload: Dict[str, Any]) -> str:
        result = self.db.lesson_sessions.insert_one(payload)
        return str(result.inserted_id)

    def log_attempt(self, payload: Dict[str, Any]) -> None:
        self.db.question_attempts.insert_one(payload)

    def append_xp(self, user_id: str, reason: str, xp_delta: int, metadata: Dict[str, Any] | None = None) -> None:
        self.db.xp_ledger.insert_one(
            {
                "user_id": user_id,
                "reason": reason,
                "xp_delta": xp_delta,
                "metadata": metadata or {},
                "created_at": datetime.now(timezone.utc),
            }
        )


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@learning_api.get("/progress/home")
def get_home_progress():
    # TODO: replace demo payload by repository read with authenticated user context.
    return jsonify(
        {
            "current_level": "beginner",
            "current_sublevel": "B1 Foundations",
            "xp": 0,
            "hearts": 5,
            "streak_days": 0,
            "next_lesson_id": "b1_foundations_lesson_01",
        }
    )


@learning_api.post("/lesson/start")
def start_lesson():
    payload = request.get_json(silent=True) or {}
    sublevel = payload.get("sublevel")
    lesson_id = payload.get("lesson_id")

    if not sublevel or not lesson_id:
        return jsonify({"error": "sublevel and lesson_id are required"}), 400

    return jsonify(
        {
            "session_id": f"demo_{lesson_id}",
            "status": "started",
            "xp_grant": 2,
            "started_at": _utc_now().isoformat(),
        }
    )


@learning_api.post("/lesson/answer")
def submit_answer():
    payload = request.get_json(silent=True) or {}
    required = ["session_id", "question_id", "selected", "correct_answer"]
    missing = [field for field in required if field not in payload]
    if missing:
        return jsonify({"error": f"Missing fields: {', '.join(missing)}"}), 400

    correct = payload["selected"] == payload["correct_answer"]
    return jsonify(
        {
            "correct": correct,
            "xp_delta": 10 if correct else 0,
            "hearts_delta": 0 if correct else -1,
            "evaluated_at": _utc_now().isoformat(),
        }
    )


@learning_api.post("/lesson/finish")
def finish_lesson():
    payload = request.get_json(silent=True) or {}
    session_id = payload.get("session_id")
    score_percent = int(payload.get("score_percent", 0))

    if not session_id:
        return jsonify({"error": "session_id is required"}), 400

    return jsonify(
        {
            "session_id": session_id,
            "status": "completed",
            "score_percent": score_percent,
            "sublevel_unlocked": score_percent >= 80,
            "awards": {
                "xp_bonus": 25 if score_percent == 100 else 0,
                "badges": ["first_sign"] if score_percent >= 70 else [],
            },
        }
    )


@learning_api.get("/quests/today")
def get_quests_today():
    return jsonify(
        {
            "quests": [
                {"id": "dq_1", "title": "Complete 2 lessons", "reward_xp": 30},
                {"id": "dq_2", "title": "Maintain streak today", "reward_xp": 20},
                {"id": "dq_3", "title": "Get 8 correct answers", "reward_xp": 35},
            ]
        }
    )


@learning_api.get("/leaderboard/weekly")
def get_weekly_leaderboard():
    return jsonify({"window": "weekly", "items": []})
