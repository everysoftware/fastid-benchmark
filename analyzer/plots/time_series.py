from pathlib import Path
from typing import Dict

from matplotlib import pyplot as plt


def plot_time_series(ts_data: Dict, output_path: Path, max_plots=12):
    """Построение временных рядов RPS и задержки для ключевых тестов."""
    # Выберем несколько репрезентативных тестов
    keys = list(ts_data.keys())
    # Сортируем по системе, ядрам, пользователям
    keys.sort(key=lambda x: (ts_data[x]['info']['system'], ts_data[x]['info']['cpu'], ts_data[x]['info']['users']))
    # Ограничим количество
    keys = keys[:max_plots]

    n = len(keys)
    if n == 0:
        return
    cols = min(3, n)
    rows = (n + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols, figsize=(5 * cols, 4 * rows))
    if rows == 1 and cols == 1:
        axes = [axes]
    else:
        axes = axes.flatten()

    for idx, key in enumerate(keys):
        ax = axes[idx]
        data = ts_data[key]['df']
        info = ts_data[key]['info']
        # RPS по времени
        if 'Requests/s' in data.columns and 'datetime' in data.columns:
            ax.plot(data['datetime'], data['Requests/s'], label='RPS', color='blue', alpha=0.7)
            ax2 = ax.twinx()
            if '95%' in data.columns:
                ax2.plot(data['datetime'], data['95%'], label='P95 latency', color='red', alpha=0.7, linestyle='--')
                ax2.set_ylabel('P95 Latency (ms)', color='red')
            ax.set_xlabel('Time')
            ax.set_ylabel('RPS', color='blue')
            ax.set_title(f"{info['system'].capitalize()} | {info['cpu']} cores | {info['users']} users")
            ax.legend(loc='upper left')
            ax.grid(True, alpha=0.3)
    # Скрыть лишние оси
    for j in range(n, len(axes)):
        axes[j].set_visible(False)

    plt.tight_layout()
    plt.savefig(output_path / 'time_series.png', dpi=150)
    plt.close()
