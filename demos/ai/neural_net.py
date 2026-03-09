#!/usr/bin/env python3
"""
RevMatrix AI Demo — Neural Network Training
============================================
Trains a multi-layer neural network from scratch using only NumPy.
No TensorFlow/PyTorch needed — pure math, fully transparent.

Install:
    pip install numpy

Run:
    python neural_net.py
    python neural_net.py --epochs 50 --hidden 64 32 --lr 0.01
"""

import numpy as np
import argparse
import time
import json
import os
from typing import Optional

# ─── ACTIVATION FUNCTIONS ───────────────────────────────────────────
def relu(z):         return np.maximum(0, z)
def relu_deriv(z):   return (z > 0).astype(float)
def sigmoid(z):      return 1 / (1 + np.exp(-np.clip(z, -500, 500)))
def sigmoid_deriv(z): return sigmoid(z) * (1 - sigmoid(z))
def softmax(z):
    e = np.exp(z - z.max(axis=1, keepdims=True))
    return e / e.sum(axis=1, keepdims=True)


# ─── LOSSES ─────────────────────────────────────────────────────────
def binary_crossentropy(y_pred, y_true):
    y_true = y_true.reshape(-1, 1)
    return -np.mean(y_true * np.log(y_pred + 1e-8) + (1 - y_true) * np.log(1 - y_pred + 1e-8))

def accuracy(y_pred, y_true):
    return np.mean((y_pred.flatten() > 0.5) == y_true.flatten())


# ─── NEURAL NETWORK ─────────────────────────────────────────────────
class RevMatrixNN:
    """
    Fully-connected neural network built from scratch.
    Architecture: configurable hidden layers + sigmoid output.
    """
    def __init__(self, layer_sizes: list[int], learning_rate: float = 0.01, seed: int = 42):
        np.random.seed(seed)
        self.lr = learning_rate
        self.layer_sizes = layer_sizes
        self.weights = []
        self.biases  = []
        self.history = {"train_loss": [], "val_loss": [], "val_acc": []}

        # He initialization (better for ReLU)
        for i in range(len(layer_sizes) - 1):
            fan_in = layer_sizes[i]
            w = np.random.randn(fan_in, layer_sizes[i+1]) * np.sqrt(2.0 / fan_in)
            b = np.zeros((1, layer_sizes[i+1]))
            self.weights.append(w)
            self.biases.append(b)

    @property
    def param_count(self) -> int:
        return sum(w.size + b.size for w, b in zip(self.weights, self.biases))

    def forward(self, X: np.ndarray) -> tuple[np.ndarray, list]:
        """Forward pass — returns output and all layer activations."""
        activations = [X]
        a = X
        for i, (w, b) in enumerate(zip(self.weights, self.biases)):
            z = a @ w + b
            # Last layer → sigmoid, hidden layers → ReLU
            a = sigmoid(z) if i == len(self.weights) - 1 else relu(z)
            activations.append(a)
        return a, activations

    def backward(self, activations: list, y: np.ndarray) -> None:
        """Backpropagation — update weights via gradient descent."""
        m = y.shape[0]
        y = y.reshape(-1, 1)

        # Output layer gradient
        delta = activations[-1] - y

        for i in reversed(range(len(self.weights))):
            dW = activations[i].T @ delta / m
            db = delta.mean(axis=0, keepdims=True)
            self.weights[i] -= self.lr * dW
            self.biases[i]  -= self.lr * db
            if i > 0:
                delta = (delta @ self.weights[i].T) * relu_deriv(
                    activations[i] @ self.weights[i].T + self.biases[i]
                    if False else activations[i]
                )

    def train(self, X_train, y_train, X_val, y_val,
              epochs: int = 20, batch_size: int = 64,
              verbose: bool = True) -> dict:

        n_batches = max(1, len(X_train) // batch_size)
        print(f"\n  Architecture : {' → '.join(map(str, self.layer_sizes))}")
        print(f"  Parameters   : {self.param_count:,}")
        print(f"  Learning rate: {self.lr}")
        print(f"  Epochs       : {epochs}")
        print(f"  Batch size   : {batch_size}")
        print(f"  Train samples: {len(X_train)}")
        print(f"  Val samples  : {len(X_val)}\n")

        for epoch in range(1, epochs + 1):
            # Shuffle
            idx = np.random.permutation(len(X_train))
            X_shuf, y_shuf = X_train[idx], y_train[idx]

            # Mini-batch gradient descent
            epoch_loss = 0
            for b in range(n_batches):
                Xb = X_shuf[b*batch_size:(b+1)*batch_size]
                yb = y_shuf[b*batch_size:(b+1)*batch_size]
                out, activations = self.forward(Xb)
                epoch_loss += binary_crossentropy(out, yb)
                self.backward(activations, yb)

            # Validation
            val_out, _ = self.forward(X_val)
            val_loss = binary_crossentropy(val_out, y_val)
            val_acc  = accuracy(val_out, y_val)
            train_loss = epoch_loss / n_batches

            self.history["train_loss"].append(float(train_loss))
            self.history["val_loss"].append(float(val_loss))
            self.history["val_acc"].append(float(val_acc))

            if verbose and (epoch % 2 == 0 or epoch == 1 or epoch == epochs):
                bar_len = 20
                filled  = int(val_acc * bar_len)
                bar     = "█" * filled + "░" * (bar_len - filled)
                trend   = "↓" if len(self.history["val_loss"]) > 1 and val_loss < self.history["val_loss"][-2] else " "
                print(f"  Epoch {epoch:3d}/{epochs}  "
                      f"loss: {train_loss:.4f}  "
                      f"val_loss: {val_loss:.4f} {trend}  "
                      f"acc: [{bar}] {val_acc:.1%}")

        return self.history

    def predict(self, X: np.ndarray) -> np.ndarray:
        out, _ = self.forward(X)
        return (out.flatten() > 0.5).astype(int)

    def save(self, path: str) -> None:
        """Save model weights to JSON."""
        model_data = {
            "layer_sizes": self.layer_sizes,
            "learning_rate": self.lr,
            "weights": [w.tolist() for w in self.weights],
            "biases":  [b.tolist() for b in self.biases],
            "history": self.history
        }
        with open(path, "w") as f:
            json.dump(model_data, f)
        print(f"\n  ✓ Model saved → {path}")


# ─── DATASET GENERATOR ──────────────────────────────────────────────
def make_dataset(n_samples: int = 1000, n_features: int = 8, seed: int = 42) -> tuple:
    """
    Synthetic binary classification dataset.
    Label = 1 if weighted sum of first 3 features > 0.
    """
    np.random.seed(seed)
    X = np.random.randn(n_samples, n_features)
    # Non-linear decision boundary
    y = ((X[:, 0] * 2 + X[:, 1] - X[:, 2] ** 2 + np.random.randn(n_samples) * 0.5) > 0).astype(float)

    # Normalize
    X = (X - X.mean(0)) / (X.std(0) + 1e-8)

    # Split
    split = int(n_samples * 0.8)
    return X[:split], y[:split], X[split:], y[split:]


# ─── ENTRY POINT ────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RevMatrix Neural Network Demo")
    parser.add_argument("--epochs",   type=int,   default=20,             help="Training epochs")
    parser.add_argument("--hidden",   type=int,   nargs="+", default=[64, 32], help="Hidden layer sizes")
    parser.add_argument("--lr",       type=float, default=0.01,           help="Learning rate")
    parser.add_argument("--samples",  type=int,   default=1000,           help="Dataset size")
    parser.add_argument("--save",     type=str,   default=None,           help="Save model to path")
    args = parser.parse_args()

    print("\n\033[96m╔══════════════════════════════════════════════╗\033[0m")
    print("\033[96m║   RevMatrix AI Engine — Neural Network       ║\033[0m")
    print("\033[96m╚══════════════════════════════════════════════╝\033[0m")

    print(f"\n\033[92m[*]\033[0m Generating dataset ({args.samples} samples)...")
    X_train, y_train, X_val, y_val = make_dataset(args.samples)
    print(f"\033[92m[*]\033[0m Class balance — Train: {y_train.mean():.1%} positive")

    layer_sizes = [X_train.shape[1]] + args.hidden + [1]
    model = RevMatrixNN(layer_sizes, learning_rate=args.lr)

    t0 = time.time()
    history = model.train(X_train, y_train, X_val, y_val, epochs=args.epochs)
    elapsed = time.time() - t0

    # Final metrics
    final_acc = history["val_acc"][-1]
    best_acc  = max(history["val_acc"])
    print(f"\n\033[92m[+]\033[0m Training complete in {elapsed:.1f}s")
    print(f"\033[92m[+]\033[0m Final accuracy  : {final_acc:.1%}")
    print(f"\033[92m[+]\033[0m Best accuracy   : {best_acc:.1%}")
    print(f"\033[92m[+]\033[0m Final val loss  : {history['val_loss'][-1]:.4f}")

    if args.save:
        model.save(args.save)
    else:
        default_path = "/tmp/revmatrix_model.json"
        model.save(default_path)
