import re
import warnings
from pathlib import Path

import seaborn as sns
from matplotlib import pyplot as plt

warnings.filterwarnings('ignore')

RESULTS_BASE = Path("./results")  # корень с папками cpu_1, cpu_2, ...
OUTPUT_DIR = Path("report")
OUTPUT_DIR.mkdir(exist_ok=True)

# Системы и их цвета
SYSTEMS = {
    'keycloak': {'color': '#1f77b4', 'name': 'Keycloak'},
    'fastid': {'color': '#ff7f0e', 'name': 'FastID'},
}

# Параметры тестов (из имени файла)
PATTERN = re.compile(
    r'(?P<system>\w+)_(?P<users>\d+)_(?P<ramp>\d+)_(?P<duration>\d+)_stats\.csv$'
)


def setup_style():
    """Настройка стиля графиков."""
    sns.set_style("whitegrid")
    plt.rcParams['figure.figsize'] = (12, 8)
    plt.rcParams['font.size'] = 12
    plt.rcParams['axes.titlesize'] = 14
    plt.rcParams['axes.labelsize'] = 12
