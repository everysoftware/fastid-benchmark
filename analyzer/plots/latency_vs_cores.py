from pathlib import Path

import pandas as pd
from matplotlib import pyplot as plt

from analyzer.config import SYSTEMS


def plot_latency_vs_cores(df: pd.DataFrame, output_path: Path, latency: str = "p95"):
    """Latency в зависимости от ядер."""
    latency_title = latency.upper()
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    axes = axes.flatten()
    user_levels = sorted(df["users"].unique())

    for idx, users in enumerate(user_levels[:4]):
        ax = axes[idx]
        subset = df[df["users"] == users]
        for system in SYSTEMS:
            sys_df = subset[subset["system"] == system]
            if not sys_df.empty:
                sys_df = sys_df.sort_values("cpu_cores")
                ax.plot(sys_df["cpu_cores"], sys_df[latency],
                        marker="s", label=SYSTEMS[system]["name"],
                        color=SYSTEMS[system]["color"], linewidth=2)
        ax.set_title(f"{latency_title} Latency vs CPU cores (users={users})")
        ax.set_xlabel("CPU cores")
        ax.set_ylabel(f"{latency_title} Latency (ms)")
        ax.legend()
        ax.grid(True, alpha=0.3)

    for j in range(len(user_levels), 4):
        axes[j].set_visible(False)
    plt.tight_layout()
    plt.savefig(output_path / f"latency_vs_cores_{latency}.png", dpi=150)
    plt.close()
