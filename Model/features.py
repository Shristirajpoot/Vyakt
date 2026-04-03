from __future__ import annotations

from typing import Iterable, List

import numpy as np

NUM_HANDS = 2
LANDMARKS_PER_HAND = 21
COORDS_PER_LANDMARK = 3
FEATURE_SIZE = NUM_HANDS * LANDMARKS_PER_HAND * COORDS_PER_LANDMARK
SEQUENCE_LENGTH = 30


def _flatten_hand(hand_landmarks) -> List[float]:
    values: List[float] = []
    for point in hand_landmarks.landmark:
        values.extend([float(point.x), float(point.y), float(point.z)])
    return values


def extract_landmark_features(results) -> List[float]:
    """Return a fixed-length [left_hand, right_hand] feature vector."""
    left_hand = [0.0] * (LANDMARKS_PER_HAND * COORDS_PER_LANDMARK)
    right_hand = [0.0] * (LANDMARKS_PER_HAND * COORDS_PER_LANDMARK)
    unknown_hands: List[List[float]] = []

    if not results or not results.multi_hand_landmarks:
        return left_hand + right_hand

    for idx, hand_landmarks in enumerate(results.multi_hand_landmarks[:NUM_HANDS]):
        flattened = _flatten_hand(hand_landmarks)
        hand_label = None

        if getattr(results, "multi_handedness", None) and idx < len(results.multi_handedness):
            handedness = results.multi_handedness[idx]
            if handedness.classification:
                hand_label = handedness.classification[0].label

        if hand_label == "Left":
            left_hand = flattened
        elif hand_label == "Right":
            right_hand = flattened
        else:
            unknown_hands.append(flattened)

    if left_hand == [0.0] * len(left_hand) and unknown_hands:
        left_hand = unknown_hands.pop(0)
    if right_hand == [0.0] * len(right_hand) and unknown_hands:
        right_hand = unknown_hands.pop(0)

    features = left_hand + right_hand
    if len(features) != FEATURE_SIZE:
        raise ValueError(f"Unexpected feature length {len(features)}; expected {FEATURE_SIZE}")
    return features


def normalize_sequence(sequence: Iterable[Iterable[float]]) -> np.ndarray:
    data = np.asarray(list(sequence), dtype=np.float32)
    max_abs = np.abs(data).max()
    if max_abs > 0:
        data = data / max_abs
    return data
