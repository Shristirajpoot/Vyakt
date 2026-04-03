import argparse
import os
import pickle
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np

from features import FEATURE_SIZE, SEQUENCE_LENGTH, extract_landmark_features

VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".webm"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create sequential gesture dataset from class folders.")
    parser.add_argument("--data-dir", default="data", help="Directory with one folder per class.")
    parser.add_argument("--output", default="artifacts/data_seq.pickle", help="Output pickle path.")
    parser.add_argument("--sequence-length", type=int, default=SEQUENCE_LENGTH)
    return parser.parse_args()


def get_mp_solutions():
    solutions = getattr(mp, "solutions", None)
    if solutions is None:
        raise RuntimeError(
            "mediapipe.solutions is unavailable in this environment. "
            "Install a legacy Hands-compatible build, e.g. pip install mediapipe==0.10.14"
        )
    return solutions


def is_video(path: Path) -> bool:
    return path.suffix.lower() in VIDEO_EXTENSIONS


def is_image(path: Path) -> bool:
    return path.suffix.lower() in IMAGE_EXTENSIONS


def process_video(video_path: Path, hands, sequence_length: int) -> list[list[float]]:
    cap = cv2.VideoCapture(str(video_path))
    sequence: list[list[float]] = []

    while len(sequence) < sequence_length and cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = hands.process(frame_rgb)
        sequence.append(extract_landmark_features(results))

    cap.release()

    if len(sequence) < sequence_length:
        sequence.extend([[0.0] * FEATURE_SIZE for _ in range(sequence_length - len(sequence))])
    return sequence[:sequence_length]


def process_image(image_path: Path, hands, sequence_length: int) -> list[list[float]]:
    frame = cv2.imread(str(image_path))
    if frame is None:
        return [[0.0] * FEATURE_SIZE for _ in range(sequence_length)]

    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = hands.process(frame_rgb)
    features = extract_landmark_features(results)
    return [features[:] for _ in range(sequence_length)]


def main() -> None:
    args = parse_args()
    data_dir = Path(args.data_dir)
    output_path = Path(args.output)

    if not data_dir.exists() or not data_dir.is_dir():
        raise FileNotFoundError(f"Data directory not found: {data_dir}")

    class_dirs = sorted([p for p in data_dir.iterdir() if p.is_dir()])
    if not class_dirs:
        raise ValueError(f"No class folders found in: {data_dir}")

    mp_solutions = get_mp_solutions()
    mp_hands = mp_solutions.hands
    hands_video = mp_hands.Hands(
        static_image_mode=False,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5,
        max_num_hands=2,
    )
    hands_image = mp_hands.Hands(
        static_image_mode=True,
        min_detection_confidence=0.5,
        max_num_hands=2,
    )

    data: list[list[list[float]]] = []
    labels: list[int] = []
    label_map = [class_dir.name for class_dir in class_dirs]

    for label_index, class_dir in enumerate(class_dirs):
        class_files = sorted([p for p in class_dir.iterdir() if p.is_file()])
        if not class_files:
            continue

        for file_path in class_files:
            if is_video(file_path):
                sequence = process_video(file_path, hands_video, args.sequence_length)
            elif is_image(file_path):
                sequence = process_image(file_path, hands_image, args.sequence_length)
            else:
                continue

            data.append(sequence)
            labels.append(label_index)

    hands_video.close()
    hands_image.close()

    if not data:
        raise ValueError("No valid image/video samples found to build dataset.")

    data_array = np.asarray(data, dtype=np.float32)
    labels_array = np.asarray(labels, dtype=np.int64)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        pickle.dump(
            {
                "data": data_array,
                "labels": labels_array,
                "label_map": label_map,
                "sequence_length": int(args.sequence_length),
                "feature_size": int(FEATURE_SIZE),
            },
            f,
        )

    print(f"Saved dataset: {output_path}")
    print(f"Samples: {len(data_array)}")
    print(f"Classes: {len(label_map)} -> {label_map}")
    print(f"Shape: {data_array.shape}")


if __name__ == "__main__":
    main()
