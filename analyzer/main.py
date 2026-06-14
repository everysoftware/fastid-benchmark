from analyzer.config import RESULTS_BASE, OUTPUT_DIR, setup_style
from analyzer.insights import generate_insights
from analyzer.plots.latency_distribution import plot_latency_distribution
from analyzer.plots.latency_vs_cores import plot_latency_vs_cores
from analyzer.plots.rps_vs_cores import plot_rps_vs_cores
from analyzer.plots.rps_vs_users import plot_rps_vs_users
from analyzer.plots.scalability_heatmap import plot_scalability_heatmap
from analyzer.plots.time_series import plot_time_series
from analyzer.utils import find_all_result_files, aggregate_results, load_time_series, generate_summary_table


# ==================== ОСНОВНАЯ ФУНКЦИЯ ====================
def main():
    print("🔍 Scanning for result files...")
    results = find_all_result_files(RESULTS_BASE)
    print(f"Found {len(results)} test results.")

    if not results:
        print("No result files found. Please ensure you have cpu_*/ folders with CSV files.")
        return

    print("📊 Aggregating data...")
    df_aggregated = aggregate_results(results)
    print(f"Aggregated {len(df_aggregated)} test runs.")

    # Сохраним сводную таблицу
    df_aggregated.to_csv(OUTPUT_DIR / 'aggregated_results.csv', index=False)

    print("📈 Generating visualizations...")
    setup_style()
    plot_rps_vs_cores(df_aggregated, OUTPUT_DIR)
    plot_latency_vs_cores(df_aggregated, OUTPUT_DIR)
    plot_scalability_heatmap(df_aggregated, OUTPUT_DIR)
    plot_rps_vs_users(df_aggregated, OUTPUT_DIR)
    plot_latency_distribution(df_aggregated, OUTPUT_DIR)

    print("📉 Processing time series...")
    ts_data = load_time_series(results)
    if ts_data:
        plot_time_series(ts_data, OUTPUT_DIR)

    print("📋 Generating summary table...")
    summary_df = generate_summary_table(df_aggregated)
    summary_df.to_csv(OUTPUT_DIR / 'max_performance_summary.csv', index=False)

    print("💡 Generating insights...")
    insights = generate_insights(df_aggregated, summary_df)
    with open(OUTPUT_DIR / 'insights.md', 'w', encoding='utf-8') as f:
        f.write(insights)

    print(f"✅ Analysis complete! Report saved to {OUTPUT_DIR.absolute()}")
    print("   - aggregated_results.csv  (all metrics)")
    print("   - max_performance_summary.csv")
    print("   - insights.md  (text conclusions)")
    print("   - *.png  (plots)")


if __name__ == "__main__":
    main()
