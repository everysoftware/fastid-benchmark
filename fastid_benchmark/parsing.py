import csv


def get_metrics(csv_file):
    with open(csv_file) as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["Name"] == "Aggregated":
                rps = float(row["Requests/s"])
                p95 = float(row["95%"])

                return rps, p95
    return None, None

# Использование:
rps_token, _ = get_metrics("results/token_fastid_stats.csv")
_, p95_userinfo = get_metrics("results/userinfo_fastid_stats.csv")
print(f"FastID: Token RPS = {rps_token}, Userinfo p95 = {p95_userinfo} ms")
