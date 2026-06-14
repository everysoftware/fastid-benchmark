from pathlib import Path

import pandas as pd
from matplotlib import pyplot as plt

from analyzer.config import SYSTEMS


def plot_rps_vs_users(df: pd.DataFrame, output_path: Path):
    """RPS в зависимости от числа пользователей для фиксированного числа ядер."""
    cpu_levels = sorted(df["cpu_cores"].unique())
    # Выберем ключевые: 1, 4, 16 (если есть)
    selected_cpus = [c for c in [1, 4, 8, 16] if c in cpu_levels]
    fig, axes = plt.subplots(1, len(selected_cpus), figsize=(15, 5))
    if len(selected_cpus) == 1:
        axes = [axes]

    for idx, cpu in enumerate(selected_cpus):
        ax = axes[idx]
        subset = df[df["cpu_cores"] == cpu]
        for system in SYSTEMS:
            sys_df = subset[subset["system"] == system].sort_values("users")
            if not sys_df.empty:
                ax.plot(sys_df["users"], sys_df["rps"],
                        marker="o", label=SYSTEMS[system]["name"],
                        color=SYSTEMS[system]["color"], linewidth=2)
        ax.set_title(f"RPS vs concurrent users ({cpu} cores)")
        ax.set_xlabel("Users")
        ax.set_ylabel("RPS")
        ax.legend()
        ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_path / "rps_vs_users.png", dpi=150)
    plt.close()
