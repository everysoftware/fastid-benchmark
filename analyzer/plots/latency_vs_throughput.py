from matplotlib import pyplot as plt

from analyzer.config import SYSTEMS


def plot_latency_vs_throughput(df, output_dir):
    plt.figure(figsize=(10,8))
    for system in df["system"].unique():
        sub = df[df["system"] == system]
        sizes = 30 + sub["cpu_cores"] * 10
        plt.scatter(sub["rps"], sub["p95"], s=sizes, alpha=0.7,
                    label=SYSTEMS[system]["name"], color=SYSTEMS[system]["color"])
    plt.xlabel("Throughput (RPS)")
    plt.ylabel("P95 Latency (ms)")
    plt.title("P95 Latency vs Throughput\n(bubble size = CPU cores)")
    plt.legend()
    plt.grid(True, linestyle="--", alpha=0.6)
    plt.tight_layout()
    plt.savefig(output_dir / "latency_vs_throughput.png", dpi=150)
    plt.close()
