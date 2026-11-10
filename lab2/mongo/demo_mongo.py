import sys
from datetime import date
from pprint import pprint

sys.path.insert(0, ".")
from db import get_mongo_db  # noqa: E402
from repositories.mongo_profile_repository import MongoProfileRepository  # noqa: E402

STUDENT_ID = 42


def print_doc(doc):
    doc = dict(doc)
    doc["grades"] = doc["grades"][:3] + [f"... ще {len(doc['grades']) - 3}"]
    pprint(doc, width=110, sort_dicts=False)


def main():
    db = get_mongo_db()
    repo = MongoProfileRepository(db)
    col = db["student_profiles"]

    print("\n===== 1. Профіль студента =====")
    print_doc(repo.get_profile(STUDENT_ID))

    print("\n===== 2. Додавання оцінки =====")
    print("до:   ", repo.get_profile(STUDENT_ID)["stats"])
    repo.add_grade(STUDENT_ID, 2, 8, 100, date.today(), subject_name="Бази даних 1",
                   credits=5, semester_name="2025/2026 весна")
    print("після:", repo.get_profile(STUDENT_ID)["stats"])

    print("\n===== 3. Новий тип досягнення (hackathon) =====")
    repo.add_achievement(STUDENT_ID, {
        "type": "hackathon", "title": "Lviv IT Hackathon 2026", "date": date(2026, 10, 12),
        "team": "NullPointers", "prize_uah": 15000, "stack": ["Python", "MongoDB", "Redis"],
    })
    pprint(col.find_one({"_id": STUDENT_ID}, {"last_name": 1, "achievements": {"$slice": -2}}),
           width=110, sort_dicts=False)

    print("\n===== 4. Хто був на хакатонах зі стеком MongoDB =====")
    for d in col.find({"achievements": {"$elemMatch": {"type": "hackathon", "stack": "MongoDB"}}},
                      {"first_name": 1, "last_name": 1, "group.name": 1}):
        print(d)

    print("\n===== 5. Документ без групи (має бути помилка валідації) =====")
    try:
        col.insert_one({"_id": -1, "first_name": "Без", "last_name": "Групи"})
    except Exception as e:
        print("Помилка:", type(e).__name__)

    print("\n===== 6. Кількість досягнень за типами =====")
    for row in col.aggregate([
        {"$unwind": "$achievements"},
        {"$group": {"_id": "$achievements.type", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]):
        print(row)

    print("\n===== 7. Видалення хакатону =====")
    col.update_one({"_id": STUDENT_ID}, {"$pull": {"achievements": {"type": "hackathon"}}})
    print("хакатонів:", col.count_documents({"_id": STUDENT_ID, "achievements.type": "hackathon"}))


if __name__ == "__main__":
    main()
