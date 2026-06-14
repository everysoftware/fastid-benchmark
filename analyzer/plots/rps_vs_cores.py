from pathlib import Path

import pandas as pd
from matplotlib import pyplot as plt

from analyzer.config import SYSTEMS


def plot_rps_vs_cores(df: pd.DataFrame, output_path: Path):
    """График RPS в зависимости от числа ядер для разных уровней нагрузки."""
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    axes = axes.flatten()
    user_levels = sorted(df['users'].unique())

    for idx, users in enumerate(user_levels[:4]):  # макс 4 графика
        ax = axes[idx]
        subset = df[df['users'] == users]
        for system in SYSTEMS:
            sys_df = subset[subset['system'] == system]
            if not sys_df.empty:
                sys_df = sys_df.sort_values('cpu_cores')
                ax.plot(sys_df['cpu_cores'], sys_df['rps'],
                        marker='o', label=SYSTEMS[system]['name'],
                        color=SYSTEMS[system]['color'], linewidth=2)
        ax.set_title(f'RPS vs CPU cores (users={users})')
        ax.set_xlabel('CPU cores')
        ax.set_ylabel('Requests per second')
        ax.legend()
        ax.grid(True, alpha=0.3)

    # Убираем пустые подграфики
    for j in range(len(user_levels), 4):
        axes[j].set_visible(False)

    plt.tight_layout()
    plt.savefig(output_path / 'rps_vs_cores.png', dpi=150)
    plt.close()
