import argparse
from collections import deque
from pathlib import Path

import cv2
import mediapipe as mp
import torch

from features import FEATURE_SIZE, SEQUENCE_LENGTH, extract_landmark_features, normalize_sequence
from gesture_model import GestureTransformer


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Realtime sign inference from webcam.")
    parser.add_argument("--checkpoint", default="artifacts/gesture_transformer.pth")
    parser.add_argument("--camera-index", type=int, default=0)
    parser.add_argument("--min-detection-confidence", type=float, default=0.5)
    return parser.parse_args()


def get_mp_solutions():
    solutions = getattr(mp, "solutions", None)
    if solutions is None:
        raise RuntimeError(
            "mediapipe.solutions is unavailable. Install a Hands-compatible build "
            "(for example: pip install mediapipe==0.10.14)."
        )
    return solutions


def load_model(checkpoint_path: Path, device: torch.device):
    if not checkpoint_path.exists():
        raise FileNotFoundError(f"Checkpoint not found: {checkpoint_path}")

    checkpoint = torch.load(checkpoint_path, map_location=device)
    model = GestureTransformer(
        input_dim=int(checkpoint.get("feature_size", FEATURE_SIZE)),
        seq_length=int(checkpoint.get("sequence_length", SEQUENCE_LENGTH)),
        num_classes=int(checkpoint.get("num_classes", len(checkpoint.get("label_map", [])) or 1)),
    )
    model.load_state_dict(checkpoint["model_state_dict"])
    model.to(device)
    model.eval()
    return model, checkpoint


def main() -> None:
    args = parse_args()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    model, checkpoint = load_model(Path(args.checkpoint), device)
    label_map = checkpoint.get("label_map", [])
    sequence_length = int(checkpoint.get("sequence_length", SEQUENCE_LENGTH))

    mp_solutions = get_mp_solutions()
    mp_hands = mp_solutions.hands
    mp_drawing = mp_solutions.drawing_utils

    hands = mp_hands.Hands(
        static_image_mode=False,
        min_detection_confidence=args.min_detection_confidence,
        min_tracking_confidence=0.5,
        max_num_hands=2,
    )

    cap = cv2.VideoCapture(args.camera_index)
    sequence = deque(maxlen=sequence_length)
    prediction_text = ""

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = hands.process(frame_rgb)

        if results.multi_hand_landmarks:
            for hand_landmarks in results.multi_hand_landmarks:
                mp_drawing.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)

        sequence.append(extract_landmark_features(results))

        if len(sequence) == sequence_length:
            input_np = normalize_sequence(sequence)
            input_tensor = torch.tensor(input_np, dtype=torch.float32, device=device).unsqueeze(0)

            with torch.no_grad():
                logits = model(input_tensor)
                pred_idx = int(torch.argmax(logits, dim=1).item())

            if label_map and pred_idx < len(label_map):
                prediction_text = str(label_map[pred_idx])
            else:
                prediction_text = str(pred_idx)

        if prediction_text:
            cv2.putText(
                frame,
                f"Prediction: {prediction_text}",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.9,
                (0, 255, 0),
                2,
                cv2.LINE_AA,
            )

        cv2.imshow("Sign Language Recognition", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    hands.close()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
