from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from analyzer.config import RESULTS_BASE


def load_authentik_data(base_path: Path, target_users=100):
    """Загружает данные Authentik для заданного числа пользователей."""
    rows = []
    for cpu_folder in base_path.glob("cpu_*"):
        cpu = int(cpu_folder.name.split("_")[1])
        for stats_file in cpu_folder.glob("authentik_*_stats.csv"):
            # Парсим имя файла: authentik_100_10_60_stats.csv
            parts = stats_file.stem.split("_")
            if len(parts) >= 4 and parts[0] == "authentik":
                users = int(parts[1])
                if users != target_users:
                    continue
                df = pd.read_csv(stats_file)
                agg = df[df["Name"] == "Aggregated"].iloc[0] if not df[df["Name"] == "Aggregated"].empty else df.iloc[
                    -1]
                rows.append({
                    "system": "authentik",
                    "cpu_cores": cpu,
                    "p95": agg["95%"],
                    "users": users
                })
    return pd.DataFrame(rows)


def plot_baseline_latency_vs_cores(df_aggregated, output_dir, target_users=100):
    """
    Строит график P95 latency vs CPU cores для baseline (target_users=100)
    с использованием данных из df_aggregated (для FastID и Keycloak) и
    дополнительной загрузки данных Authentik.
    """
    # Берём данные FastID и Keycloak из уже загруженного датафрейма
    df_baseline = df_aggregated[df_aggregated["users"] == target_users].copy()
    if df_baseline.empty:
        print(f"Нет данных для {target_users} пользователей в df_aggregated.")
        return

    # Загружаем данные Authentik
    df_authentik = load_authentik_data(RESULTS_BASE, target_users)  # путь к папке с cpu_*
    if df_authentik.empty:
        print("Данные Authentik не найдены. График будет только для FastID и Keycloak.")

    # Объединяем
    df_all = pd.concat([df_baseline, df_authentik], ignore_index=True)

    # Цвета и названия
    colors = {"fastid": "#2ca02c", "keycloak": "#1f77b4", "authentik": "#d62728"}
    labels = {"fastid": "FastID", "keycloak": "Keycloak", "authentik": "Authentik"}

    plt.figure(figsize=(10, 6))
    for system in df_all["system"].unique():
        sys_df = df_all[df_all["system"] == system].sort_values("cpu_cores")
        if sys_df.empty:
            continue
        plt.plot(sys_df["cpu_cores"], sys_df["p95"], marker="o", linewidth=2,
                 label=labels.get(system, system), color=colors.get(system, "gray"))

    plt.yscale("log")
    plt.xlabel("CPU cores")
    plt.ylabel("P95 Latency (ms) - log scale")
    plt.title(f"Baseline: P95 Latency vs CPU cores (users = {target_users})")
    plt.grid(True, which="both", linestyle="--", alpha=0.5)
    plt.legend()
    plt.tight_layout()
    plt.savefig(output_dir / f"baseline_latency_vs_cores_log_{target_users}.png", dpi=150)
    plt.close()

    # Дополнительно: столбчатая диаграмма для максимальных ядер (например, 16)
    max_cores = df_all["cpu_cores"].max()
    df_max = df_all[df_all["cpu_cores"] == max_cores]
    if not df_max.empty:
        plt.figure(figsize=(8, 5))
        systems = df_max["system"].map(labels).values
        latencies = df_max["p95"].values
        bars = plt.bar(systems, latencies, color=[colors[s] for s in df_max["system"]])
        plt.yscale("log")
        plt.ylabel("P95 Latency (ms) - log scale")
        plt.title(f"P95 Latency at {max_cores} cores, {target_users} users")
        for bar, val in zip(bars, latencies):
            plt.text(bar.get_x() + bar.get_width() / 2, val + 100, f"{val:.0f} ms",
                     ha="center", va="bottom", fontsize=9)
        plt.tight_layout()
        plt.savefig(output_dir / f"baseline_latency_bar_{target_users}_{max_cores}.png", dpi=150)
        plt.close()
