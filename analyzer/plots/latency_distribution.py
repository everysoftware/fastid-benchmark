from collections.abc import Sequence
from pathlib import Path

import numpy as np
import pandas as pd
from matplotlib import pyplot as plt

from analyzer.config import SYSTEMS


def plot_latency_distribution(df: pd.DataFrame, output_path: Path, cpu_cores: int = 1, target_users=2000,
                              percentiles: Sequence[str] = ("p50", "p75", "p90", "p95", "p99")):
    """Сравнение перцентилей задержки для каждой системы на максимальной нагрузке."""
    if target_users not in df["users"].unique():
        target_users = df["users"].max()

    subset = df[(df["users"] == target_users) & (df["cpu_cores"] == cpu_cores)]
    if subset.empty:
        return

    systems = subset["system"].unique()
    x = np.arange(len(percentiles))
    width = 0.25
    multiplier = 0

    fig, ax = plt.subplots(figsize=(12, 6))
    for system in systems:
        sys_data = subset[subset["system"] == system]
        values = [sys_data.iloc[0][p] for p in percentiles]
        offset = width * multiplier
        ax.bar(x + offset, values, width, label=SYSTEMS[system]["name"], color=SYSTEMS[system]["color"])
        multiplier += 1

    ax.set_ylabel("Latency (ms)")
    ax.set_title(f'Latency percentiles on max cores ({subset.iloc[0]["cpu_cores"]} cores, {target_users} users)')
    ax.set_xticks(x + width)
    ax.set_xticklabels(percentiles)
    ax.legend()
    ax.grid(True, axis="y", alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_path / f"latency_distribution_{cpu_cores}_{target_users}.png", dpi=150)
    plt.close()
