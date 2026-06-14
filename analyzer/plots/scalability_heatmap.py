from pathlib import Path

import pandas as pd
import seaborn as sns
from matplotlib import pyplot as plt


def plot_scalability_heatmap(df: pd.DataFrame, output_path: Path):
    """Тепловая карта RPS по системе и ядрам (фиксированная нагрузка, например 1000 users)."""
    # Выберем нагрузку 1000 users (или самую высокую доступную)
    target_users = 2000
    if target_users not in df['users'].unique():
        target_users = df['users'].max()

    subset = df[df['users'] == target_users]
    pivot = subset.pivot_table(index='system', columns='cpu_cores', values='rps', aggfunc='first')

    plt.figure(figsize=(10, 6))
    sns.heatmap(pivot, annot=True, fmt='.0f', cmap='YlOrRd', linewidths=0.5)
    plt.title(f'RPS Heatmap (users={target_users})')
    plt.xlabel('CPU cores')
    plt.ylabel('System')
    plt.tight_layout()
    plt.savefig(output_path / 'rps_heatmap.png', dpi=150)
    plt.close()
