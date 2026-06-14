from pathlib import Path

import matplotlib.pyplot as plt


def plot_time_series(ts_data: dict, output_path: Path, selected_combinations: list[tuple[str, int, int]]):
    if not selected_combinations:
        print("Нет выбранных комбинаций для временных рядов.")
        return

    n = len(selected_combinations)
    # Определяем сетку: 2x2 для 4 графиков, или 3x2 для 6 и т.д.
    cols = 2 if n <= 4 else 3
    rows = (n + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols, figsize=(6 * cols, 4 * rows))
    if rows == 1 and cols == 1:
        axes = [axes]
    else:
        axes = axes.flatten()

    for idx, (system, cpu, users) in enumerate(selected_combinations):
        ax = axes[idx]
        # Ищем ключ в ts_data
        found = None
        for key, val in ts_data.items():
            if val["info"]["system"] == system and val["info"]["cpu"] == cpu and val["info"]["users"] == users:
                found = val
                break
        if not found:
            ax.text(0.5, 0.5, f"No data\n{system} {cpu}c {users}u", ha="center", va="center")
            ax.set_axis_off()
            continue

        data = found["df"]
        # RPS по времени
        if "Requests/s" in data.columns and "datetime" in data.columns:
            ax.plot(data["datetime"], data["Requests/s"], label="RPS", color="blue", alpha=0.7)
            ax2 = ax.twinx()
            if "95%" in data.columns:
                ax2.plot(data["datetime"], data["95%"], label="P95 latency", color="red", alpha=0.7, linestyle="--")
                ax2.set_ylabel("P95 Latency (ms)", color="red")
            ax.set_xlabel("Time")
            ax.set_ylabel("RPS", color="blue")
            ax.set_title(f"{system.capitalize()} | {cpu} cores | {users} users")
            ax.legend(loc="upper left")
            ax.grid(True, alpha=0.3)

    # Скрыть лишние оси
    for j in range(n, len(axes)):
        axes[j].set_visible(False)

    plt.tight_layout()
    plt.savefig(output_path / "time_series.png", dpi=150)
    plt.close()
