#!/usr/bin/env python3
"""Build Phase 1 and Phase 2 curriculum artifacts from sign assets."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[1]
ASSET_DIR = ROOT / "static" / "assets"
OUT_DIR = ROOT / "learning" / "curriculum"

BEGINNER_HINTS = {
    "hello", "bye", "thank", "thank you", "good", "help", "please",
    "yes", "no", "i", "you", "we", "my", "your", "name", "home",
    "what", "where", "who", "when", "why", "how", "learn", "study",
    "happy", "sad", "safe", "welcome", "day", "time", "work",
}

INTERMEDIATE_HINTS = {
    "language", "talk", "walk", "wash", "eat", "change", "right",
    "wrong", "whole", "world", "computer", "engineer", "distance",
    "before", "after", "again", "better", "best", "beautiful",
    "without", "with", "from", "keep", "more", "next", "sound",
}

ADVANCED_HINTS = {
    "do not", "does not", "against", "whose", "yourself", "alone",
    "invent", "glitter", "college", "homepage", "cannot",
}

BEGINNER_SUBLEVELS = ["B1 Foundations", "B2 Daily Core", "B3 Starter Phrases"]
INTERMEDIATE_SUBLEVELS = ["I1 Actions", "I2 Concepts", "I3 Sentences"]
ADVANCED_SUBLEVELS = ["A1 Complex Meaning", "A2 Scenario Language", "A3 Fluency Sprint"]


@dataclass
class VocabItem:
    word: str
    source_file: str
    category: str
    difficulty_score: int
    level: str
    sublevel: str = ""


def list_asset_words() -> List[str]:
    words = []
    if not ASSET_DIR.exists():
        return words

    for path in sorted(ASSET_DIR.glob("*.mp4")):
        words.append(path.stem)
    return words


def normalized(word: str) -> str:
    return " ".join(word.lower().split())


def category_of(word: str) -> str:
    if len(word) == 1 and word.isalpha():
        return "alphabet"
    if len(word) == 1 and word.isdigit():
        return "number"
    if " " in word:
        return "phrase"
    return "word"


def score_word(word: str) -> int:
    key = normalized(word)
    tokens = key.split()

    score = 1
    if category_of(word) == "alphabet":
        score = 0
    elif category_of(word) == "number":
        score = 1
    else:
        score += len(tokens) - 1
        score += max(0, len(key) - 4) // 5

    if key in BEGINNER_HINTS:
        score -= 2
    if key in INTERMEDIATE_HINTS:
        score += 1
    if key in ADVANCED_HINTS:
        score += 3

    return max(0, score)


def assign_levels_by_percentile(items: List[VocabItem]) -> None:
    """Assign levels using score percentile buckets for better curriculum balance."""
    ranked = sorted(items, key=lambda x: (x.difficulty_score, normalized(x.word)))
    total = len(ranked)
    if total == 0:
        return

    beginner_cutoff = int(total * 0.50)
    intermediate_cutoff = int(total * 0.80)

    for idx, item in enumerate(ranked):
        if idx < beginner_cutoff:
            item.level = "beginner"
        elif idx < intermediate_cutoff:
            item.level = "intermediate"
        else:
            item.level = "advanced"


def split_sublevels(items: List[VocabItem], names: List[str]) -> Dict[str, List[VocabItem]]:
    sorted_items = sorted(items, key=lambda x: (x.difficulty_score, normalized(x.word)))
    total = len(sorted_items)
    if total == 0:
        return {name: [] for name in names}

    size = (total + len(names) - 1) // len(names)
    result: Dict[str, List[VocabItem]] = {name: [] for name in names}

    for idx, item in enumerate(sorted_items):
        group_idx = min(idx // size, len(names) - 1)
        sub_name = names[group_idx]
        item.sublevel = sub_name
        result[sub_name].append(item)

    return result


def build_items(words: List[str]) -> List[VocabItem]:
    items: List[VocabItem] = []
    for w in words:
        cat = category_of(w)
        score = score_word(w)
        items.append(
            VocabItem(
                word=w,
                source_file=f"{w}.mp4",
                category=cat,
                difficulty_score=score,
                level="beginner",
            )
        )

    assign_levels_by_percentile(items)
    return items


def write_csv(items: List[VocabItem]) -> None:
    csv_path = OUT_DIR / "phase1_vocabulary.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["word", "source_file", "category", "difficulty_score", "level", "sublevel"])
        for item in sorted(items, key=lambda x: (x.level, x.sublevel, normalized(x.word))):
            writer.writerow([
                item.word,
                item.source_file,
                item.category,
                item.difficulty_score,
                item.level,
                item.sublevel,
            ])


def write_phase1_audit(items: List[VocabItem]) -> None:
    counts = {
        "total": len(items),
        "alphabet": sum(1 for x in items if x.category == "alphabet"),
        "number": sum(1 for x in items if x.category == "number"),
        "word": sum(1 for x in items if x.category == "word"),
        "phrase": sum(1 for x in items if x.category == "phrase"),
        "beginner": sum(1 for x in items if x.level == "beginner"),
        "intermediate": sum(1 for x in items if x.level == "intermediate"),
        "advanced": sum(1 for x in items if x.level == "advanced"),
    }

    audit = {
        "phase": "Phase 1 - Dataset Audit",
        "source": str(ASSET_DIR.relative_to(ROOT)),
        "summary": counts,
        "difficulty_rubric": {
            "base": "length + token_count",
            "beginner_bonus": "basic daily terms are easier",
            "advanced_bonus": "negation/abstract/multi-word terms are harder",
        },
    }

    with (OUT_DIR / "phase1_dataset_audit.json").open("w", encoding="utf-8") as handle:
        json.dump(audit, handle, indent=2)


def write_phase2_plan(items: List[VocabItem], level_splits: Dict[str, Dict[str, List[VocabItem]]]) -> None:
    def words_of(vocab_items: List[VocabItem]) -> List[str]:
        return [v.word for v in sorted(vocab_items, key=lambda x: normalized(x.word))]

    levels = []
    order = ["beginner", "intermediate", "advanced"]

    for level_name in order:
        sub_map = level_splits[level_name]
        sublevels = []
        all_items = []
        for sublevel_name, vocab_items in sub_map.items():
            all_items.extend(vocab_items)
            sublevels.append(
                {
                    "name": sublevel_name,
                    "word_count": len(vocab_items),
                    "unlock_rule": "Complete >= 80% lesson score in previous sublevel",
                    "words": words_of(vocab_items),
                }
            )

        levels.append(
            {
                "name": level_name,
                "word_count": len(all_items),
                "unlock_rule": "Previous level completed with average score >= 75%",
                "sublevels": sublevels,
            }
        )

    phase2 = {
        "phase": "Phase 2 - Level and Sub-level Design",
        "levels": levels,
    }

    with (OUT_DIR / "phase2_levels.json").open("w", encoding="utf-8") as handle:
        json.dump(phase2, handle, indent=2)


def write_readme(items: List[VocabItem], level_splits: Dict[str, Dict[str, List[VocabItem]]]) -> None:
    lines = [
        "# Phase 1 + Phase 2 Deliverables",
        "",
        "Generated by: scripts/build_curriculum.py",
        "",
        "## Files",
        "- phase1_dataset_audit.json",
        "- phase1_vocabulary.csv",
        "- phase2_levels.json",
        "",
        "## Snapshot",
        f"- Total assets (mp4): {len(items)}",
        f"- Beginner words: {sum(1 for x in items if x.level == 'beginner')}",
        f"- Intermediate words: {sum(1 for x in items if x.level == 'intermediate')}",
        f"- Advanced words: {sum(1 for x in items if x.level == 'advanced')}",
        "",
        "## Sub-level counts",
    ]

    for level_name in ["beginner", "intermediate", "advanced"]:
        lines.append(f"- {level_name.title()}:")
        for sub_name, vocab in level_splits[level_name].items():
            lines.append(f"  - {sub_name}: {len(vocab)}")

    lines.append("")
    lines.append("## Next")
    lines.append("- Phase 3: Define XP economy, streak rules, and badge triggers")
    lines.append("- Phase 4: Build UI screens from phase2_levels.json")

    (OUT_DIR / "README_PHASE1_PHASE2.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    words = list_asset_words()
    items = build_items(words)

    beginner_items = [x for x in items if x.level == "beginner"]
    intermediate_items = [x for x in items if x.level == "intermediate"]
    advanced_items = [x for x in items if x.level == "advanced"]

    level_splits = {
        "beginner": split_sublevels(beginner_items, BEGINNER_SUBLEVELS),
        "intermediate": split_sublevels(intermediate_items, INTERMEDIATE_SUBLEVELS),
        "advanced": split_sublevels(advanced_items, ADVANCED_SUBLEVELS),
    }

    write_phase1_audit(items)
    write_phase2_plan(items, level_splits)

    flattened = []
    for level_name in ["beginner", "intermediate", "advanced"]:
        for sublevel_name in level_splits[level_name]:
            flattened.extend(level_splits[level_name][sublevel_name])

    write_csv(flattened)
    write_readme(items, level_splits)

    print("Generated curriculum files in learning/curriculum")


if __name__ == "__main__":
    main()
