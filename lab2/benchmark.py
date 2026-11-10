import argparse
import json
import random
import statistics
import time
from datetime import date
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from db import get_connection, get_mongo_db  # noqa: E402
from mongo.migrate_to_mongo import migrate  # noqa: E402
from repositories.jsonb_profile_repository import JsonbProfileRepository  # noqa: E402
from repositories.mongo_profile_repository import MongoProfileRepository  # noqa: E402
from repositories.sql_profile_repository import (  # noqa: E402
    SqlProfileRepository, SqlOneQueryProfileRepository)

RESULTS = Path("results")

TESTS = {
    "T1": "профіль за id",
    "T2": "профілі групи",
    "T3": "додати оцінку",
    "T4": "перейменувати дисципліну",
    "T5": "сер. бал по дисциплінах",
    "T6": "переможці олімпіад",
    "T7": "топ-20 факультету",
}


def measure(fn, inputs, warmup=()):
    for x in warmup:
        fn(x)
    times = []
    rows = 0
    for x in inputs:
        start = time.perf_counter()
        result = fn(x)
        times.append((time.perf_counter() - start) * 1000)
        if isinstance(result, list):
            rows = len(result)
        elif isinstance(result, dict):
            rows = 1
    times.sort()
    return {
        "median_ms": round(statistics.median(times), 3),
        "p95_ms": round(times[int(len(times) * 0.95)], 3),
        "mean_ms": round(statistics.mean(times), 3),
        "ops_per_s": round(1000 / statistics.mean(times), 1),
        "n": len(times),
        "rows": rows,
    }


def generate(scale):
    print(f"Генерація {scale} студентів у PostgreSQL...")
    conn = get_connection(autocommit=True)
    cur = conn.cursor()
    cur.execute("CALL sp_generate_data(%s, 30)", (scale,))
    cur.execute(Path("sql/04_indexes.sql").read_text(encoding="utf-8"))
    cur.execute("VACUUM ANALYZE")
    conn.close()
    print("Перенесення в MongoDB...")
    migrate()


def check_same_data(sql, mongo, ids):
    for i in ids:
        a = sql.get_profile(i)
        b = mongo.get_profile(i)
        assert a["stats"]["grades_count"] == b["stats"]["grades_count"]
        assert abs(float(a["stats"]["avg_grade"]) - b["stats"]["avg_grade"]) < 0.01
        assert len(a["achievements"]) == len(b["achievements"])
    print("Дані в SQL і MongoDB однакові")


def run_tests(scale, quick):
    rnd = random.Random(2026)
    k = 0.2 if quick else 1
    groups_count = scale // 25

    conn = get_connection(autocommit=True)
    cur = conn.cursor()
    mdb = get_mongo_db()
    sql = SqlProfileRepository(cur)
    sql1 = SqlOneQueryProfileRepository(cur)
    jsonb = JsonbProfileRepository(cur)
    mongo = MongoProfileRepository(mdb)

    check_same_data(sql, mongo, rnd.sample(range(1, scale + 1), 20))

    # однакові вхідні дані для всіх баз
    ids = rnd.sample(range(1, scale + 1), int(1000 * k))
    warm_ids = rnd.sample(range(1, scale + 1), 100)
    groups = [rnd.randint(1, groups_count) for _ in range(int(200 * k))]
    faculties = [1 + i % 5 for i in range(int(50 * k))]

    cur.execute("SELECT id, name, credits FROM subjects")
    subjects = {r["id"]: r for r in cur.fetchall()}
    cur.execute("SELECT id, name FROM semesters")
    semesters = {r["id"]: r["name"] for r in cur.fetchall()}

    def new_grade():
        sub = rnd.randint(1, 60)
        sem = rnd.randint(1, 8)
        return dict(student_id=rnd.randint(1, scale), subject_id=sub, semester_id=sem,
                    grade=rnd.randint(50, 100), grade_date=date(2026, 11, 1),
                    subject_name=subjects[sub]["name"], credits=subjects[sub]["credits"],
                    semester_name=semesters[sem])
    grades = [new_grade() for _ in range(int(500 * k))]

    results = {}

    def run(test, repos, fn, inputs, warmup=()):
        results[test] = {}
        for repo in repos:
            r = measure(lambda x: fn(repo, x), inputs, warmup)
            results[test][repo.name] = r
            print(f"{test} {repo.name:<18} median {r['median_ms']:>10.3f} мс | "
                  f"p95 {r['p95_ms']:>10.3f} мс | рядків {r['rows']}")

    # спочатку читання, потім запис
    run("T1", [sql, sql1, jsonb, mongo], lambda r, x: r.get_profile(x), ids, warm_ids)
    run("T2", [sql, sql1, jsonb, mongo], lambda r, x: r.get_group_profiles(x), groups, groups[:10])
    run("T5", [sql, jsonb, mongo], lambda r, x: r.avg_by_subject(), range(3 if quick else 5), range(1))
    run("T6", [sql, jsonb, mongo], lambda r, x: r.find_olympiad_winners("international", 1),
        range(int(50 * k)), range(3))
    run("T7", [sql, jsonb, mongo], lambda r, x: r.faculty_top(x), faculties, range(1, 6))
    run("T3", [sql, jsonb, mongo], lambda r, x: r.add_grade(**x), grades, grades[:10])

    stamp = int(time.time())
    run("T4", [sql, jsonb, mongo],
        lambda r, x: r.rename_subject(x, f"{subjects[x]['name']} {stamp}"),
        [7] if quick else [7, 23, 41])

    conn.close()
    return results


def storage():
    conn = get_connection(autocommit=True)
    cur = conn.cursor()
    tables = ["faculties", "specialties", "groups", "students", "subjects", "semesters",
              "grades", "achievements", "olympiad_details", "certificate_details",
              "publication_details", "publication_coauthors"]
    cur.execute(
        "SELECT SUM(pg_total_relation_size(t::regclass)) AS total, "
        "SUM(pg_indexes_size(t::regclass)) AS idx FROM unnest(%s::text[]) t",
        (tables,),
    )
    sql_size = cur.fetchone()
    cur.execute("SELECT pg_total_relation_size('student_profiles_jsonb') AS total, "
                "pg_indexes_size('student_profiles_jsonb') AS idx")
    jsonb_size = cur.fetchone()
    conn.close()
    stats = list(get_mongo_db()["student_profiles"].aggregate(
        [{"$collStats": {"storageStats": {}}}]))[0]["storageStats"]

    mb = lambda b: round(int(b) / 1024 / 1024, 1)  # noqa: E731
    return {
        "SQL (12 таблиць)": {"data_mb": mb(sql_size["total"] - sql_size["idx"]),
                             "index_mb": mb(sql_size["idx"])},
        "PostgreSQL JSONB": {"data_mb": mb(jsonb_size["total"] - jsonb_size["idx"]),
                             "index_mb": mb(jsonb_size["idx"])},
        "MongoDB": {"data_mb": mb(stats["storageSize"]), "index_mb": mb(stats["totalIndexSize"])},
    }


def save_summary(all_results):
    lines = ["# Результати", ""]
    for scale, data in all_results.items():
        lines += [f"## {scale} студентів", "",
                  "| Тест | База | median, мс | p95, мс | оп/с | рядків |",
                  "|---|---|---:|---:|---:|---:|"]
        for test in TESTS:
            for name, r in data["tests"][test].items():
                lines.append(f"| {test} {TESTS[test]} | {name} | {r['median_ms']} | "
                             f"{r['p95_ms']} | {r['ops_per_s']} | {r['rows']} |")
        lines += ["", "| Розмір | дані, МБ | індекси, МБ |", "|---|---:|---:|"]
        for name, s in data["storage"].items():
            lines.append(f"| {name} | {s['data_mb']} | {s['index_mb']} |")
        lines.append("")
    (RESULTS / "summary.md").write_text("\n".join(lines), encoding="utf-8")


COLORS = {"SQL (3 запити)": "#2a6fdb", "SQL (1 запит)": "#8fb3ef",
          "PostgreSQL JSONB": "#e08a1e", "MongoDB": "#2e9e5b"}


def save_charts(all_results):
    for scale, data in all_results.items():
        fig, axes = plt.subplots(1, 7, figsize=(22, 4.8))
        for ax, test in zip(axes, TESTS):
            names = list(data["tests"][test])
            values = [data["tests"][test][n]["median_ms"] for n in names]
            bars = ax.bar(range(len(names)), values, color=[COLORS[n] for n in names])
            ax.set_title(f"{test}: {TESTS[test]}", fontsize=9)
            ax.set_xticks([])
            for b, v in zip(bars, values):
                ax.text(b.get_x() + b.get_width() / 2, b.get_height(), f"{v:.2f}",
                        ha="center", va="bottom", fontsize=7)
        axes[0].set_ylabel("median, мс")
        fig.legend([plt.Rectangle((0, 0), 1, 1, color=c) for c in COLORS.values()],
                   COLORS.keys(), loc="lower center", ncol=4, frameon=False)
        fig.suptitle(f"Медіанний час операції, {scale} студентів (менше = краще)")
        fig.tight_layout(rect=(0, 0.08, 1, 0.92))
        fig.savefig(RESULTS / f"chart_{scale}.png", dpi=120)
        plt.close(fig)

    if len(all_results) > 1:
        scales = sorted(all_results, key=int)
        fig, axes = plt.subplots(1, 3, figsize=(15, 4.5))
        for ax, test in zip(axes, ["T1", "T4", "T5"]):
            for name in all_results[scales[0]]["tests"][test]:
                ax.plot([int(s) for s in scales],
                        [all_results[s]["tests"][test][name]["median_ms"] for s in scales],
                        marker="o", label=name, color=COLORS[name])
            ax.set_title(f"{test}: {TESTS[test]}")
            ax.set_xlabel("студентів")
            ax.set_ylabel("median, мс")
            ax.set_yscale("log")
            ax.grid(alpha=0.3)
        axes[0].legend(fontsize=8)
        fig.tight_layout()
        fig.savefig(RESULTS / "chart_scaling.png", dpi=120)
        plt.close(fig)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scales", type=int, nargs="+", default=[10000, 100000])
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--skip-generate", action="store_true")
    args = parser.parse_args()

    RESULTS.mkdir(exist_ok=True)
    path = RESULTS / "results.json"
    all_results = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}

    for scale in args.scales:
        print(f"\n========== {scale} студентів ==========")
        if not args.skip_generate:
            generate(scale)
        all_results[str(scale)] = {"storage": storage(), "tests": run_tests(scale, args.quick)}
        path.write_text(json.dumps(all_results, ensure_ascii=False, indent=2), encoding="utf-8")

    save_summary(all_results)
    save_charts(all_results)
    print("\nГотово: results/summary.md, results/chart_*.png")


if __name__ == "__main__":
    main()
