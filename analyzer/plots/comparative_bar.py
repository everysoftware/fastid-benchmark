import numpy as np
from matplotlib import pyplot as plt

from analyzer.config import SYSTEMS


def plot_bar_comparison(df, output_dir, ram_estimates, max_cpu=1, target_users=2000):
    sub = df[(df["cpu_cores"] == max_cpu) & (df["users"] == target_users)]
    systems = sub["system"].unique()
    metrics = {
        "Max RPS": [sub[sub["system"] == s]["rps"].values[0] if not sub[sub["system"] == s].empty else 0 for s in
                    systems],
        "P95 Latency (ms)": [sub[sub["system"] == s]["p95"].values[0] if not sub[sub["system"] == s].empty else 0 for s
                             in systems],
    }
    metrics["Memory (MB)"] = [ram_estimates.get(s, 0) for s in systems]

    x = np.arange(len(systems))
    width = 0.25
    multiplier = 0
    fig, ax = plt.subplots(figsize=(10, 6))
    for attr, values in metrics.items():
        offset = width * multiplier
        ax.bar(x + offset, values, width, label=attr)
        multiplier += 1
    ax.set_ylabel("Value")
    ax.set_title(f"Comparative Performance on {max_cpu} cores, {target_users} users")
    ax.set_xticks(x + width)
    ax.set_xticklabels([SYSTEMS[s]["name"] for s in systems])
    ax.legend()
    ax.grid(True, axis="y", linestyle="--", alpha=0.6)
    plt.tight_layout()
    plt.savefig(output_dir / f"comparative_bar_{max_cpu}_{target_users}.png", dpi=150)
    plt.close()
