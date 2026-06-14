from matplotlib import pyplot as plt

from analyzer.config import SYSTEMS


def plot_boxplot_latency(df, output_dir, max_cpu = 1, target_users = 2000):
    """Box plot: latency distribution (using percentiles)."""
    sub = df[(df["cpu_cores"] == max_cpu) & (df["users"] == target_users)]
    data = []
    labels = []
    systems_order = []
    for system in sub["system"].unique():
        row = sub[sub["system"] == system].iloc[0]
        percentiles = [row["p50"], row["p75"], row["p90"], row["p95"], row["p99"]]
        data.append(percentiles)
        labels.append(SYSTEMS[system]["name"])
        systems_order.append(system)

    fig, ax = plt.subplots(figsize=(8, 6))
    bp = ax.boxplot(data, patch_artist=True, showmeans=True)
    ax.set_xticklabels(labels)
    for box, system in zip(bp["boxes"], systems_order):
        box.set_facecolor(SYSTEMS[system]["color"])
    ax.set_title(f"Latency distribution (percentiles) – {max_cpu} cores, {target_users} users")
    ax.set_ylabel("Latency (ms)")
    ax.grid(axis="y", linestyle="--", alpha=0.6)
    plt.tight_layout()
    plt.savefig(output_dir / f"boxplot_latency_{max_cpu}_{target_users}.png", dpi=150)
    plt.close()
