import argparse
import random
import pickle
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from sklearn.metrics import confusion_matrix
from sklearn.model_selection import train_test_split

from gesture_model import GestureTransformer


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train gesture Transformer model.")
    parser.add_argument("--data", default="artifacts/data_seq.pickle", help="Path to dataset pickle.")
    parser.add_argument("--output", default="artifacts/gesture_transformer.pth", help="Path to save checkpoint.")
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

    if data.ndim != 3:
        raise ValueError(f"Expected data shape [N, T, F], got {data.shape}")

    data = normalize_data(data)

    x_train, x_val, y_train, y_val = train_test_split(
        data,
        labels,
        test_size=args.val_size,
        random_state=args.seed,
        stratify=labels,
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
        "sequence_length": seq_length,
        "feature_size": feature_size,
        "num_classes": num_classes,
        "seed": args.seed,
        "best_val_acc": best_val_acc,
        "normalization": "per_sample_max_abs",
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

    print(f"Saved model checkpoint: {output_path}")
    print(f"Best validation accuracy: {best_val_acc:.4f}")
    print("Validation confusion matrix:")
    print(cm)
    print("Per-class validation accuracy:")
    for class_name, class_acc in per_class_accuracy.items():
        print(f"  {class_name}: {class_acc:.4f}")


if __name__ == "__main__":
    main()
