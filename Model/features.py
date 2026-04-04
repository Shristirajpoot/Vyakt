from __future__ import annotations

from typing import Iterable, List

import numpy as np

NUM_HANDS = 2
LANDMARKS_PER_HAND = 21
COORDS_PER_LANDMARK = 3
FEATURE_SIZE = NUM_HANDS * LANDMARKS_PER_HAND * COORDS_PER_LANDMARK
SEQUENCE_LENGTH = 30
HAND_FEATURE_SIZE = LANDMARKS_PER_HAND * COORDS_PER_LANDMARK
ZERO_FEATURE_VECTOR = [0.0] * FEATURE_SIZE


def _flatten_hand(hand_landmarks) -> List[float]:
    values: List[float] = []
    for point in hand_landmarks.landmark:
        values.extend([float(point.x), float(point.y), float(point.z)])
    if len(values) != HAND_FEATURE_SIZE:
        values = (values + ([0.0] * HAND_FEATURE_SIZE))[:HAND_FEATURE_SIZE]
    return values


def extract_landmark_features(results) -> List[float]:
    """Return a fixed-length [left_hand, right_hand] feature vector."""
    left_hand = [0.0] * HAND_FEATURE_SIZE
    right_hand = [0.0] * HAND_FEATURE_SIZE
    unknown_hands: List[List[float]] = []

    if not results or not results.multi_hand_landmarks:
        return ZERO_FEATURE_VECTOR.copy()

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

    if left_hand == [0.0] * HAND_FEATURE_SIZE and unknown_hands:
        left_hand = unknown_hands.pop(0)
    if right_hand == [0.0] * HAND_FEATURE_SIZE and unknown_hands:
        right_hand = unknown_hands.pop(0)

    features = left_hand + right_hand
    if len(features) != FEATURE_SIZE:
        features = (features + ZERO_FEATURE_VECTOR)[:FEATURE_SIZE]
    return features


def pad_or_trim_sequence(
    sequence: Iterable[Iterable[float]],
    sequence_length: int = SEQUENCE_LENGTH,
    feature_size: int = FEATURE_SIZE,
) -> np.ndarray:
    fixed_frames: List[List[float]] = []
    for frame in sequence:
        frame_values = [float(v) for v in frame]
        if len(frame_values) != feature_size:
            frame_values = (frame_values + ([0.0] * feature_size))[:feature_size]
        fixed_frames.append(frame_values)

    if len(fixed_frames) < sequence_length:
        fixed_frames.extend([[0.0] * feature_size for _ in range(sequence_length - len(fixed_frames))])

    fixed_frames = fixed_frames[:sequence_length]
    return np.asarray(fixed_frames, dtype=np.float32)


def normalize_sequence(
    sequence: Iterable[Iterable[float]],
    sequence_length: int = SEQUENCE_LENGTH,
    feature_size: int = FEATURE_SIZE,
) -> np.ndarray:
    data = pad_or_trim_sequence(
        sequence=sequence,
        sequence_length=sequence_length,
        feature_size=feature_size,
    )
    max_abs = float(np.abs(data).max()) if data.size else 0.0
    if max_abs > 0.0:
        data = data / max_abs
    return data


def is_no_hand_feature_vector(feature_vector: Iterable[float], eps: float = 1e-8) -> bool:
    values = np.asarray(list(feature_vector), dtype=np.float32)
    if values.size == 0:
        return True
    return bool(np.max(np.abs(values)) <= eps)
