from datetime import datetime

import pandas as pd

from analyzer.config import SYSTEMS


def generate_insights(df: pd.DataFrame, summary_df: pd.DataFrame) -> str:
    """Генерирует текстовые выводы на основе данных."""
    insights = []
    insights.append("# PERFORMANCE BENCHMARK INSIGHTS\n")
    insights.append(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # 1. Абсолютная производительность на максимальных ядрах
    max_cores = df["cpu_cores"].max()
    max_load = df[df["cpu_cores"] == max_cores]
    best_system = max_load.loc[max_load["rps"].idxmax()]["system"]
    best_rps = max_load["rps"].max()
    insights.append(f"## Absolute Performance (max cores = {max_cores})\n")
    insights.append(f"- **Best system**: {SYSTEMS[best_system]['name']} with {best_rps:.0f} RPS\n")
    insights.append("- Ranking:\n")
    for system in SYSTEMS:
        sys_max = max_load[max_load["system"] == system]["rps"].max() if not max_load[
            max_load["system"] == system].empty else 0
        insights.append(f"  - {SYSTEMS[system]['name']}: {sys_max:.0f} RPS\n")

    # 2. Масштабируемость
    insights.append("\n## Scalability Analysis\n")
    for system in SYSTEMS:
        sys_df = df[df["system"] == system].sort_values("cpu_cores")
        if len(sys_df) > 1:
            base_rps = sys_df[sys_df["cpu_cores"] == sys_df["cpu_cores"].min()]["rps"].mean()
            max_rps = sys_df["rps"].max()
            scaling_factor = max_rps / base_rps if base_rps > 0 else 0
            insights.append(
                f"- **{SYSTEMS[system]['name']}**: scales {scaling_factor:.1f}x from {sys_df['cpu_cores'].min()} to {sys_df['cpu_cores'].max()} cores\n")

    # 3. Латентность при высокой нагрузке
    high_user = df["users"].max()
    high_load = df[(df["users"] == high_user) & (df["cpu_cores"] == max_cores)]
    insights.append(f"\n## Latency at high load ({high_user} users, {max_cores} cores)\n")
    for system in SYSTEMS:
        row = high_load[high_load["system"] == system]
        if not row.empty:
            p95 = row.iloc[0]["p95"]
            insights.append(f"- **{SYSTEMS[system]['name']}**: P95 = {p95:.0f} ms\n")

    # 4. Эффективность (RPS per core)
    insights.append("\n## Efficiency (RPS per core at max load)\n")
    for system in SYSTEMS:
        cores_rows = df[df["system"] == system]
        if not cores_rows.empty:
            best_efficiency_row = cores_rows.loc[(cores_rows["rps"] / cores_rows["cpu_cores"]).idxmax()]
            efficiency = best_efficiency_row["rps"] / best_efficiency_row["cpu_cores"]
            insights.append(
                f"- **{SYSTEMS[system]['name']}**: {efficiency:.0f} RPS/core at {best_efficiency_row['cpu_cores']} cores\n")

    # 5. Надёжность (наличие ошибок)
    fails = df[df["failure_count"] > 0]
    if not fails.empty:
        insights.append("\n## Reliability (failures observed)\n")
        for _, row in fails.iterrows():
            insights.append(
                f"- {SYSTEMS[row['system']]['name']} on {row['cpu_cores']} cores with {row['users']} users: {row['failure_count']} failures\n")
    else:
        insights.append("\n## Reliability: No failures reported in any test.\n")

    return "".join(insights)
