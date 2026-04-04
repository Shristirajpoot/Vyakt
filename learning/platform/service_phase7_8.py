"""Phase 7 + 8 service helpers for gamification, personalization, and retention."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List


@dataclass
class LessonResult:
    user_id: str
    lesson_id: str
    score_percent: int
    correct_answers: int
    total_questions: int
    streak_days: int


def calculate_xp_award(result: LessonResult) -> int:
    # Baseline from phase3: lesson_start=2, correct_answer=10, perfect_bonus=25
    xp = 2 + (result.correct_answers * 10)
    if result.score_percent == 100:
        xp += 25
    if result.score_percent >= 80:
        xp += 10
    return xp


def hearts_delta(score_percent: int) -> int:
    if score_percent >= 80:
        return 0
    if score_percent >= 60:
        return -1
    return -2


def evaluate_badges(state: Dict[str, Any], result: LessonResult) -> List[str]:
    unlocked = []

    if state.get("lessons_completed", 0) == 0:
        unlocked.append("first_sign")

    if result.streak_days >= 7:
        unlocked.append("week_warrior")

    if result.score_percent == 100:
        unlocked.append("precision_pro")

    if state.get("lessons_completed", 0) + 1 >= 30:
        unlocked.append("consistent_learner")

    return unlocked


def compute_rank_score(progress: Dict[str, Any]) -> float:
    total_xp = float(progress.get("xp", 0))
    streak_days = float(progress.get("streak_days", 0))
    perfect_lessons = float(progress.get("perfect_lessons", 0))
    return (total_xp * 0.7) + (streak_days * 8.0) + (perfect_lessons * 5.0)


def recommend_next_lesson(
    current_lesson_id: str,
    available_lessons: List[str],
    weak_lesson_ids: List[str],
    streak_at_risk: bool,
) -> str:
    if weak_lesson_ids:
        return weak_lesson_ids[0]

    if streak_at_risk and current_lesson_id in available_lessons:
        return current_lesson_id

    try:
        idx = available_lessons.index(current_lesson_id)
        return available_lessons[min(idx + 1, len(available_lessons) - 1)]
    except ValueError:
        return available_lessons[0] if available_lessons else ""


def build_revision_queue(incorrect_words: List[str], cap: int = 20) -> List[str]:
    # Keep insertion order but dedupe.
    seen = set()
    queue = []
    for word in incorrect_words:
        if word in seen:
            continue
        seen.add(word)
        queue.append(word)
        if len(queue) >= cap:
            break
    return queue


def weekly_summary_payload(user_id: str, lessons_completed: int, accuracy_percent: int, xp_gained: int, new_badges: List[str]) -> Dict[str, Any]:
    return {
        "user_id": user_id,
        "week_ending": datetime.now(timezone.utc).date().isoformat(),
        "lessons_completed": lessons_completed,
        "accuracy_percent": accuracy_percent,
        "xp_gained": xp_gained,
        "new_badges": new_badges,
    }
