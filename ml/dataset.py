"""
ml/dataset.py - Elliptic Bitcoin transaction-graph loader.

The Elliptic dataset (Weber et al., 2019) is the standard public benchmark
for GNN-based fraud/Sybil detection: ~203k nodes (transactions), ~234k edges
(payment flows), 166 node features, binary labels (licit/illicit).

Download (free, Kaggle): https://www.kaggle.com/datasets/ellipticco/elliptic-data-set
Expected layout under ml/data/elliptic/:
    elliptic_txs_features.csv   (txId, f1..f166)
    elliptic_txs_edgelist.csv   (txId1, txId2)
    elliptic_txs_classes.csv    (txId, class: 1=illicit, 2=licit, unknown)
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import torch
from torch_geometric.data import Data

DATA_DIR = Path(__file__).parent / "data" / "elliptic"


def load_elliptic(data_dir: Path = DATA_DIR) -> Data:
    if not data_dir.exists():
        raise FileNotFoundError(
            f"Elliptic dataset not found at {data_dir}. "
            "Download from Kaggle (free) and place the 3 CSVs there."
        )
    feats = pd.read_csv(data_dir / "elliptic_txs_features.csv", header=None)
    edges = pd.read_csv(data_dir / "elliptic_txs_edgelist.csv", header=0)
    classes = pd.read_csv(data_dir / "elliptic_txs_classes.csv")

    feats.columns = ["txId"] + [f"f{i}" for i in range(1, feats.shape[1])]
    tx_index = {tx: i for i, tx in enumerate(feats["txId"])}

    x = torch.tensor(feats[[f"f{i}" for i in range(1, 167)]].values, dtype=torch.float)

    edge_pairs = [
        (tx_index[a], tx_index[b])
        for a, b in zip(edges["txId1"], edges["txId2"])
        if a in tx_index and b in tx_index
    ]
    edge_index = torch.tensor(np.array(edge_pairs).T, dtype=torch.long)

    label_map = {"1": 1, "2": 0}  # illicit=1, licit=0; unknown -> -1
    cls = classes["class"].astype(str).map(label_map).fillna(-1).astype(int)
    label_by_tx = dict(zip(classes["txId"], cls))
    y = torch.tensor(
        [label_by_tx.get(tx, -1) for tx in feats["txId"]], dtype=torch.long
    )

    known = y != -1
    data = Data(x=x, edge_index=edge_index, y=y)
    data.train_mask = data.val_mask = data.test_mask = None  # set in trainer
    data.known_mask = known
    return data


def split_masks(data: Data, train=0.7, val=0.1) -> Data:
    idx = torch.nonzero(data.known_mask).squeeze(1)
    perm = idx[torch.randperm(idx.size(0))]
    n_train = int(train * perm.size(0))
    n_val = int(val * perm.size(0))
    data.train_mask = torch.zeros(data.num_nodes, dtype=torch.bool)
    data.val_mask = torch.zeros(data.num_nodes, dtype=torch.bool)
    data.test_mask = torch.zeros(data.num_nodes, dtype=torch.bool)
    data.train_mask[perm[:n_train]] = True
    data.val_mask[perm[n_train:n_train + n_val]] = True
    data.test_mask[perm[n_train + n_val:]] = True
    return data
