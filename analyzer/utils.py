from pathlib import Path
from typing import Dict

import pandas as pd

from analyzer.config import PATTERN, SYSTEMS


def find_all_result_files(base_path: Path) -> Dict:
    """Обходит все папки cpu_X и собирает пути к stats.csv файлам."""
    results = {}
    for cpu_folder in base_path.glob("cpu_*"):
        cpu_num = int(cpu_folder.name.split('_')[1])
        for stats_file in cpu_folder.glob("*_stats.csv"):
            match = PATTERN.match(stats_file.name)
            if match:
                system = match.group('system')
                if system not in SYSTEMS:
                    continue
                users = int(match.group('users'))
                ramp = int(match.group('ramp'))
                duration = int(match.group('duration'))
                key = (system, cpu_num, users, ramp, duration)
                results[key] = {
                    'stats': stats_file,
                    'stats_history': stats_file.parent / stats_file.name.replace('_stats.csv', '_stats_history.csv'),
                    'failures': stats_file.parent / stats_file.name.replace('_stats.csv', '_failures.csv'),
                    'exceptions': stats_file.parent / stats_file.name.replace('_stats.csv', '_exceptions.csv'),
                    'cpu': cpu_num,
                    'system': system,
                    'users': users,
                    'ramp': ramp,
                    'duration': duration
                }
    return results


def load_stats_data(file_path: Path) -> pd.DataFrame:
    """Загружает stats.csv (итоговая строка)."""
    try:
        df = pd.read_csv(file_path)
        # Итоговая строка обычно последняя или с именем 'Aggregated'
        agg_row = df[df['Name'] == 'Aggregated']
        if not agg_row.empty:
            return agg_row.iloc[0]
        else:
            return df.iloc[-1]  # последняя строка как итог
    except Exception as e:
        print(f"Error loading {file_path}: {e}")
        return None


def load_history_data(file_path: Path) -> pd.DataFrame:
    """Загружает stats_history.csv (временной ряд)."""
    try:
        df = pd.read_csv(file_path)
        # Преобразуем Timestamp (секунды) в datetime
        if 'Timestamp' in df.columns:
            df['datetime'] = pd.to_datetime(df['Timestamp'], unit='s')
        return df
    except Exception as e:
        print(f"Error loading history {file_path}: {e}")
        return pd.DataFrame()


def aggregate_results(results_dict: Dict) -> pd.DataFrame:
    """Собирает все итоговые метрики в единую таблицу."""
    rows = []
    for key, info in results_dict.items():
        stats = load_stats_data(info['stats'])
        if stats is None:
            continue
        row = {
            'system': info['system'],
            'cpu_cores': info['cpu'],
            'users': info['users'],
            'ramp': info['ramp'],
            'duration': info['duration'],
            'request_count': stats.get('Request Count', 0),
            'failure_count': stats.get('Failure Count', 0),
            'rps': stats.get('Requests/s', 0),
            'failures_per_sec': stats.get('Failures/s', 0),
            'avg_response_ms': stats.get('Average Response Time', 0),
            'median_ms': stats.get('Median Response Time', 0),
            'p50': stats.get('50%', 0),
            'p66': stats.get('66%', 0),
            'p75': stats.get('75%', 0),
            'p80': stats.get('80%', 0),
            'p90': stats.get('90%', 0),
            'p95': stats.get('95%', 0),
            'p98': stats.get('98%', 0),
            'p99': stats.get('99%', 0),
            'p99_9': stats.get('99.9%', 0),
            'max_ms': stats.get('Max Response Time', 0),
            'avg_content_size': stats.get('Average Content Size', 0)
        }
        rows.append(row)
    df = pd.DataFrame(rows)
    return df


def load_time_series(results_dict: Dict) -> Dict:
    """Загружает временные ряды для всех тестов."""
    ts_data = {}
    for key, info in results_dict.items():
        hist_df = load_history_data(info['stats_history'])
        if not hist_df.empty:
            key_name = f"{info['system']}_cpu{info['cpu']}_users{info['users']}"
            ts_data[key_name] = {
                'df': hist_df,
                'info': info
            }
    return ts_data


def generate_summary_table(df: pd.DataFrame) -> pd.DataFrame:
    """Создаёт сводную таблицу максимальных RPS для каждой системы и числа ядер."""
    summary = []
    for system in SYSTEMS:
        sys_df = df[df['system'] == system]
        for cores in sorted(sys_df['cpu_cores'].unique()):
            cores_df = sys_df[sys_df['cpu_cores'] == cores]
            best_row = cores_df.loc[cores_df['rps'].idxmax()] if not cores_df.empty else None
            if best_row is not None:
                summary.append({
                    'System': SYSTEMS[system]['name'],
                    'CPU cores': cores,
                    'Max RPS': int(best_row['rps']),
                    'Users at max': best_row['users'],
                    'P95 (ms)': int(best_row['p95']),
                    'Failures': int(best_row['failure_count'])
                })
    return pd.DataFrame(summary)
