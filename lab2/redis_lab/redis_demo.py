import json
import random
import statistics
import sys
import time

sys.path.insert(0, ".")
from db import get_connection, get_mongo_db, get_redis  # noqa: E402
from repositories.mongo_profile_repository import MongoProfileRepository  # noqa: E402
from repositories.sql_profile_repository import SqlProfileRepository  # noqa: E402


# спочатку шукаємо в redis, якщо нема - беремо з основної бази
class CachedProfileRepository:
    def __init__(self, r, repo, ttl=300):
        self.r = r
        self.repo = repo
        self.ttl = ttl

    def get_profile(self, student_id):
        key = f"cache:profile:{student_id}"
        cached = self.r.get(key)
        if cached is not None:
            return json.loads(cached)
        doc = self.repo.get_profile(student_id)
        if doc is not None:
            self.r.set(key, json.dumps(doc, default=str, ensure_ascii=False), ex=self.ttl)
        return doc

    def invalidate(self, student_id):
        self.r.delete(f"cache:profile:{student_id}")


def measure(fn, ids):
    times = []
    for i in ids:
        start = time.perf_counter()
        fn(i)
        times.append((time.perf_counter() - start) * 1000)
    times.sort()
    return statistics.median(times), times[int(len(times) * 0.95)]


def main():
    r = get_redis()
    print("PING:", r.ping())

    mdb = get_mongo_db()
    mongo = MongoProfileRepository(mdb)
    conn = get_connection(autocommit=True)
    sql = SqlProfileRepository(conn.cursor())
    cached = CachedProfileRepository(r, mongo)

    print("\n===== 1. Кеш профілю =====")
    cached.invalidate(42)
    start = time.perf_counter()
    cached.get_profile(42)
    t1 = (time.perf_counter() - start) * 1000
    start = time.perf_counter()
    cached.get_profile(42)
    t2 = (time.perf_counter() - start) * 1000
    print(f"перше читання (MongoDB): {t1:.3f} мс, друге (Redis): {t2:.3f} мс")
    print("TTL:", r.ttl("cache:profile:42"), "с")

    print("\n===== 2. Рейтинг факультету 1 =====")
    r.delete("rating:faculty:1")
    pipe = r.pipeline()
    for d in mdb["student_profiles"].find({"group.faculty.id": 1}, {"stats.avg_grade": 1}):
        pipe.zadd("rating:faculty:1", {f"student:{d['_id']}": d["stats"]["avg_grade"]})
    pipe.execute()
    print("студентів:", r.zcard("rating:faculty:1"))
    print("топ-5:", r.zrevrange("rating:faculty:1", 0, 4, withscores=True))
    print("місце student:42:", r.zrevrank("rating:faculty:1", "student:42"))
    print("відмінників (90-100):", r.zcount("rating:faculty:1", 90, 100))

    print("\n===== 3. Лічильник і стрічка подій =====")
    for _ in range(3):
        r.incr("student:42:views")
    print("переглядів:", r.get("student:42:views"))
    for event in ["Оцінка 95: Бази даних", "Сертифікат Coursera", "Олімпіада: 2 місце"]:
        r.lpush("feed:student:42", event)
    r.ltrim("feed:student:42", 0, 49)
    print("події:", r.lrange("feed:student:42", 0, 4))

    print("\n===== 4. Читання профілю: SQL / MongoDB / Redis (1000 запитів) =====")
    n = mdb["student_profiles"].estimated_document_count()
    rnd = random.Random(7)
    ids = [rnd.randint(1, n) for _ in range(1000)]
    for i in ids:
        cached.get_profile(i)  # заповнюємо кеш
    for name, fn in [("SQL", sql.get_profile),
                     ("MongoDB", mongo.get_profile),
                     ("Redis", cached.get_profile)]:
        median, p95 = measure(fn, ids)
        print(f"{name:<8} median {median:.3f} мс | p95 {p95:.3f} мс")

    conn.close()


if __name__ == "__main__":
    main()
