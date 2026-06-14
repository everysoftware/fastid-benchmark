from analyzer.config import OUTPUT_DIR, RAM_ESTIMATES, RESULTS_BASE, setup_style
from analyzer.insights import generate_insights
from analyzer.plots.baseline_latency_vs_cores import plot_baseline_latency_vs_cores
from analyzer.plots.boxplot_latency import plot_boxplot_latency
from analyzer.plots.comparative_bar import plot_bar_comparison
from analyzer.plots.latency_distribution import plot_latency_distribution
from analyzer.plots.latency_vs_cores import plot_latency_vs_cores
from analyzer.plots.latency_vs_throughput import plot_latency_vs_throughput
from analyzer.plots.rps_vs_cores import plot_rps_vs_cores
from analyzer.plots.rps_vs_users import plot_rps_vs_users
from analyzer.plots.scalability_heatmap import plot_scalability_heatmap
from analyzer.plots.scalability_table import plot_scalability_table
from analyzer.plots.time_series import plot_time_series
from analyzer.utils import aggregate_results, find_all_result_files, generate_summary_table, load_time_series


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
    df_aggregated.to_csv(OUTPUT_DIR / "aggregated_results.csv", index=False)

    print("📈 Generating visualizations...")
    setup_style()
    plot_rps_vs_cores(df_aggregated, OUTPUT_DIR)
    plot_rps_vs_users(df_aggregated, OUTPUT_DIR)
    plot_latency_vs_throughput(df_aggregated, OUTPUT_DIR)
    plot_scalability_table(df_aggregated, OUTPUT_DIR)
    plot_baseline_latency_vs_cores(df_aggregated, OUTPUT_DIR)

    for latency in ("p95", "p99", "p50"):
        plot_latency_vs_cores(df_aggregated, OUTPUT_DIR, latency=latency)

    for target_users in (1000, 2000):
        plot_scalability_heatmap(df_aggregated, OUTPUT_DIR, target_users=target_users)

    for target_users in (1000, 2000):
        for cpu_cores in (1, 2, 4, 8, 16):
            plot_latency_distribution(df_aggregated, OUTPUT_DIR, cpu_cores=cpu_cores, target_users=target_users)

    for target_users in (2000,):
        for cpu_cores in (1, 16):
            plot_bar_comparison(df_aggregated, OUTPUT_DIR,
                                ram_estimates=RAM_ESTIMATES[(cpu_cores, target_users)], max_cpu=cpu_cores,
                                target_users=target_users)

    for target_users in (1000, 2000):
        for cpu_cores in (1, 2, 4, 8, 16):
            plot_boxplot_latency(df_aggregated, OUTPUT_DIR, max_cpu=cpu_cores, target_users=target_users)

    print("📉 Processing time series...")
    ts_data = load_time_series(results)
    if ts_data:
        plot_time_series(ts_data, OUTPUT_DIR, selected_combinations=[
            ("fastid", 1, 1000),
            ("fastid", 16, 1000),
            ("keycloak", 1, 1000),
            ("keycloak", 16, 1000)
        ])

    print("📋 Generating summary table...")
    summary_df = generate_summary_table(df_aggregated)
    summary_df.to_csv(OUTPUT_DIR / "max_performance_summary.csv", index=False)

    print("💡 Generating insights...")
    insights = generate_insights(df_aggregated, summary_df)
    with open(OUTPUT_DIR / "insights.md", "w", encoding="utf-8") as f:
        f.write(insights)

    print(f"✅ Analysis complete! Report saved to {OUTPUT_DIR.absolute()}")
    print("   - aggregated_results.csv  (all metrics)")
    print("   - max_performance_summary.csv")
    print("   - insights.md  (text conclusions)")
    print("   - *.png  (plots)")


if __name__ == "__main__":
    main()
