import argparse
import hashlib
import json
import pickle
import random
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from sklearn.metrics import confusion_matrix
from sklearn.model_selection import train_test_split

from gesture_model import GestureTransformer

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_PATH = PROJECT_ROOT / "Model" / "artifacts" / "data_seq.pickle"
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "Model" / "artifacts" / "gesture_transformer.pth"
DEFAULT_RAW_DATA_DIR = PROJECT_ROOT / "data"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train gesture Transformer model.")
    parser.add_argument("--data", default=str(DEFAULT_DATA_PATH), help="Path to dataset pickle.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_PATH), help="Path to save checkpoint.")
    parser.add_argument("--data-dir", default=str(DEFAULT_RAW_DATA_DIR), help="Raw dataset folder used to build the pickle.")
    parser.add_argument(
        "--allow-stale-dataset",
        action="store_true",
        help="Allow training even if raw data folder no longer matches the dataset pickle signature.",
    )
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=1e-3)
    parser.add_argument("--val-size", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def normalize_data(data: np.ndarray) -> np.ndarray:
    max_abs = np.max(np.abs(data), axis=(1, 2), keepdims=True)
    max_abs[max_abs == 0] = 1.0
    return data / max_abs


def build_data_signature(class_sample_counts: dict[str, int], sequence_length: int, feature_size: int) -> str:
    signature_payload = {
        "class_sample_counts": {k: int(class_sample_counts[k]) for k in sorted(class_sample_counts)},
        "sequence_length": int(sequence_length),
        "feature_size": int(feature_size),
    }
    encoded = repr(signature_payload).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def read_data_dir_signature(data_dir: Path, sequence_length: int, feature_size: int) -> str:
    if not data_dir.exists() or not data_dir.is_dir():
        raise FileNotFoundError(f"Raw data directory not found: {data_dir}")

    class_sample_counts: dict[str, int] = {}
    class_dirs = sorted(
        [p for p in data_dir.iterdir() if p.is_dir() and not p.name.startswith(".")],
        key=lambda p: p.name.lower(),
    )
    if not class_dirs:
        raise ValueError(f"No class folders found under raw data directory: {data_dir}")

    for class_dir in class_dirs:
        sample_count = sum(1 for p in class_dir.iterdir() if p.is_file())
        class_sample_counts[class_dir.name] = sample_count

    return build_data_signature(
        class_sample_counts=class_sample_counts,
        sequence_length=sequence_length,
        feature_size=feature_size,
    )


def evaluate(model, loader, criterion, device):
    model.eval()
    total_loss = 0.0
    total_correct = 0
    total_count = 0

    with torch.no_grad():
        for batch_x, batch_y in loader:
            batch_x = batch_x.to(device)
            batch_y = batch_y.to(device)
            logits = model(batch_x)
            loss = criterion(logits, batch_y)

            preds = torch.argmax(logits, dim=1)
            total_correct += (preds == batch_y).sum().item()
            total_count += batch_y.size(0)
            total_loss += loss.item() * batch_y.size(0)

    avg_loss = total_loss / max(total_count, 1)
    accuracy = total_correct / max(total_count, 1)
    return avg_loss, accuracy


def collect_predictions(model, loader, device):
    model.eval()
    y_true = []
    y_pred = []

    with torch.no_grad():
        for batch_x, batch_y in loader:
            batch_x = batch_x.to(device)
            logits = model(batch_x)
            preds = torch.argmax(logits, dim=1).cpu().numpy()
            y_pred.extend(preds.tolist())
            y_true.extend(batch_y.cpu().numpy().tolist())

    return np.asarray(y_true, dtype=np.int64), np.asarray(y_pred, dtype=np.int64)


def main() -> None:
    args = parse_args()
    set_seed(args.seed)

    data_path = Path(args.data)
    if not data_path.exists():
        raise FileNotFoundError(f"Dataset file not found: {data_path}")

    with open(data_path, "rb") as f:
        dataset = pickle.load(f)

    data = np.asarray(dataset["data"], dtype=np.float32)
    labels = np.asarray(dataset["labels"], dtype=np.int64)
    label_map = list(dataset["label_map"])
    label_to_index = {label: idx for idx, label in enumerate(label_map)}
    class_sample_counts = dataset.get("class_sample_counts", {})

    if data.ndim != 3:
        raise ValueError(f"Expected data shape [N, T, F], got {data.shape}")
    if len(label_map) == 0:
        raise ValueError("Dataset has no classes in label_map.")
    if data.shape[0] != labels.shape[0]:
        raise ValueError(f"Mismatch: data samples={data.shape[0]} labels={labels.shape[0]}")
    if np.unique(labels).size != len(label_map):
        raise ValueError(
            f"Label mismatch: unique labels in dataset={np.unique(labels).size}, label_map entries={len(label_map)}"
        )

    dataset_signature = dataset.get("data_signature")
    if dataset_signature and not args.allow_stale_dataset:
        current_signature = read_data_dir_signature(
            data_dir=Path(args.data_dir),
            sequence_length=int(dataset.get("sequence_length", data.shape[1])),
            feature_size=int(dataset.get("feature_size", data.shape[2])),
        )
        if dataset_signature != current_signature:
            raise RuntimeError(
                "Dataset pickle does not match current raw data folders. "
                "Rebuild with create_dataset.py before training, or pass --allow-stale-dataset."
            )

    data = normalize_data(data)

    class_counts = np.bincount(labels, minlength=len(label_map))
    use_stratify = bool(np.all(class_counts >= 2))

    x_train, x_val, y_train, y_val = train_test_split(
        data,
        labels,
        test_size=args.val_size,
        random_state=args.seed,
        stratify=labels if use_stratify else None,
    )

    train_dataset = torch.utils.data.TensorDataset(
        torch.tensor(x_train, dtype=torch.float32),
        torch.tensor(y_train, dtype=torch.long),
    )
    val_dataset = torch.utils.data.TensorDataset(
        torch.tensor(x_val, dtype=torch.float32),
        torch.tensor(y_val, dtype=torch.long),
    )

    train_loader = torch.utils.data.DataLoader(train_dataset, batch_size=args.batch_size, shuffle=True)
    val_loader = torch.utils.data.DataLoader(val_dataset, batch_size=args.batch_size, shuffle=False)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    seq_length = int(data.shape[1])
    feature_size = int(data.shape[2])
    num_classes = len(label_map)

    model = GestureTransformer(
        input_dim=feature_size,
        seq_length=seq_length,
        num_classes=num_classes,
    ).to(device)

    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr)
    criterion = nn.CrossEntropyLoss()

    best_val_acc = 0.0
    for epoch in range(1, args.epochs + 1):
        model.train()
        running_loss = 0.0
        sample_count = 0

        for batch_x, batch_y in train_loader:
            batch_x = batch_x.to(device)
            batch_y = batch_y.to(device)

            optimizer.zero_grad()
            logits = model(batch_x)
            loss = criterion(logits, batch_y)
            loss.backward()
            optimizer.step()

            running_loss += loss.item() * batch_y.size(0)
            sample_count += batch_y.size(0)

        train_loss = running_loss / max(sample_count, 1)
        val_loss, val_acc = evaluate(model, val_loader, criterion, device)

        if val_acc > best_val_acc:
            best_val_acc = val_acc

        print(
            f"Epoch {epoch:02d}/{args.epochs} | "
            f"train_loss={train_loss:.4f} | val_loss={val_loss:.4f} | val_acc={val_acc:.4f}"
        )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    checkpoint = {
        "model_state_dict": model.state_dict(),
        "label_map": label_map,
        "label_to_index": label_to_index,
        "sequence_length": seq_length,
        "feature_size": feature_size,
        "num_classes": num_classes,
        "seed": args.seed,
        "best_val_acc": best_val_acc,
        "normalization": "per_sample_max_abs",
        "data_signature": dataset_signature,
        "class_sample_counts": class_sample_counts,
    }

    y_true, y_pred = collect_predictions(model, val_loader, device)
    cm = confusion_matrix(y_true, y_pred, labels=list(range(num_classes)))
    per_class_accuracy = {}
    for class_idx, class_name in enumerate(label_map):
        class_total = int(cm[class_idx].sum())
        class_correct = int(cm[class_idx, class_idx])
        per_class_accuracy[class_name] = (class_correct / class_total) if class_total > 0 else 0.0

    checkpoint["confusion_matrix"] = cm.tolist()
    checkpoint["per_class_accuracy"] = per_class_accuracy
    torch.save(checkpoint, output_path)

    label_map_path = output_path.parent / "label_map.json"
    label_map_payload = {
        "index_to_label": {str(idx): label for idx, label in enumerate(label_map)},
        "label_to_index": label_to_index,
        "num_classes": num_classes,
        "sequence_length": seq_length,
        "feature_size": feature_size,
        "model_checkpoint": str(output_path.resolve()),
        "normalization": "per_sample_max_abs",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "data_signature": dataset_signature,
        "class_sample_counts": class_sample_counts,
    }
    with open(label_map_path, "w", encoding="utf-8") as f:
        json.dump(label_map_payload, f, ensure_ascii=True, indent=2)

    print(f"Saved model checkpoint: {output_path}")
    print(f"Saved label map JSON: {label_map_path}")
    print(f"Best validation accuracy: {best_val_acc:.4f}")
    if not use_stratify:
        print("Warning: train/val split is not stratified because one or more classes has <2 samples.")
    print("Validation confusion matrix:")
    print(cm)
    print("Per-class validation accuracy:")
    for class_name, class_acc in per_class_accuracy.items():
        print(f"  {class_name}: {class_acc:.4f}")


if __name__ == "__main__":
    main()
