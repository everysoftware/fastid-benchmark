import numpy as np
import pandas as pd
from matplotlib import pyplot as plt

from analyzer.config import SYSTEMS


def plot_scalability_table(df, output_dir):
    """Простая таблица масштабируемости (Scaling factor = Max RPS / RPS at 1 core)."""
    rows = []
    # Группируем по системе и количеству пользователей
    groups = df.groupby(["system", "users"])
    for (system, users), group in groups:
        group = group.sort_values("cpu_cores")
        if len(group) < 2:
            continue
        # RPS на 1 ядре
        rps_1core = group[group["cpu_cores"] == 1]["rps"].values[0] if 1 in group["cpu_cores"].values else np.nan
        if np.isnan(rps_1core):
            continue
        rps_max = group["rps"].max()
        scaling = rps_max / rps_1core
        rows.append({
            "System": SYSTEMS[system]["name"],
            "Users": users,
            "RPS at 1 core": int(rps_1core),
            "Max RPS": int(rps_max),
            "Scaling factor (max/1c)": f"{scaling:.2f}"
        })
    table_df = pd.DataFrame(rows)
    if table_df.empty:
        print("No data for scalability table.")
        return
    # Сохраняем с UTF-8
    table_df.to_csv(output_dir / "scalability_table.csv", index=False, encoding="utf-8")
    with open(output_dir / "scalability_table.txt", "w", encoding="utf-8") as f:
        f.write(table_df.to_string(index=False))
    # Графическое отображение таблицы
    fig, ax = plt.subplots(figsize=(12, len(table_df)*0.5 + 1))
    ax.axis("tight")
    ax.axis("off")
    tbl = ax.table(cellText=table_df.values, colLabels=table_df.columns, loc="center", cellLoc="center")
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(10)
    plt.title("Scalability Summary")
    plt.tight_layout()
    plt.savefig(output_dir / "scalability_table_plot.png", dpi=150)
    plt.close()
    print(f"Scalability table saved to {output_dir / 'scalability_table.csv'}")
