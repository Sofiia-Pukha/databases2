import sys
import time
from datetime import date, datetime

from pymongo import ASCENDING, DESCENDING

sys.path.insert(0, ".")
from db import get_connection, get_mongo_db  # noqa: E402

BATCH = 2000

# перевірка структури документа
VALIDATOR = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["_id", "first_name", "last_name", "group", "grades", "stats"],
        "properties": {
            "_id": {"bsonType": "number"},
            "first_name": {"bsonType": "string"},
            "last_name": {"bsonType": "string"},
            "group": {"bsonType": "object", "required": ["id", "name", "faculty", "specialty"]},
            "grades": {
                "bsonType": "array",
                "items": {
                    "bsonType": "object",
                    "required": ["subject_id", "semester_id", "grade"],
                    "properties": {"grade": {"bsonType": "number", "minimum": 0, "maximum": 100}},
                },
            },
            "achievements": {
                "bsonType": "array",
                "items": {"bsonType": "object", "required": ["type", "title", "date"]},
            },
        },
    }
}


def to_datetime(value):
    if value is None or isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    return datetime.fromisoformat(value)


def prepare(doc):
    doc["birth_date"] = to_datetime(doc["birth_date"])
    doc["updated_at"] = to_datetime(doc["updated_at"])
    doc["stats"]["avg_grade"] = float(doc["stats"]["avg_grade"])
    for g in doc["grades"]:
        g["date"] = to_datetime(g["date"])
    for a in doc["achievements"]:
        a["date"] = to_datetime(a["date"])
    return doc


def create_indexes(col):
    col.create_index([("group.id", ASCENDING)], name="ix_group")
    col.create_index([("grades.subject_id", ASCENDING)], name="ix_grades_subject")
    col.create_index([("achievements.type", ASCENDING), ("achievements.level", ASCENDING),
                      ("achievements.place", ASCENDING)], name="ix_achievements")
    col.create_index([("group.faculty.id", ASCENDING), ("stats.avg_grade", DESCENDING),
                      ("_id", ASCENDING)], name="ix_faculty_avg")


def migrate():
    mdb = get_mongo_db()
    mdb.drop_collection("student_profiles")
    mdb.create_collection("student_profiles", validator=VALIDATOR)
    col = mdb["student_profiles"]

    start = time.perf_counter()
    conn = get_connection()
    total = 0
    # серверний курсор, щоб не тягнути все в пам'ять
    with conn.cursor(name="etl") as cur:
        cur.itersize = BATCH
        cur.execute("SELECT doc FROM v_student_profile ORDER BY id")
        batch = []
        for row in cur:
            batch.append(prepare(row["doc"]))
            if len(batch) == BATCH:
                col.insert_many(batch)
                total += len(batch)
                batch = []
        if batch:
            col.insert_many(batch)
            total += len(batch)
    conn.close()

    create_indexes(col)
    print(f"Перенесено документів: {total}, час: {time.perf_counter() - start:.1f} с")
    return total


if __name__ == "__main__":
    migrate()
    doc = get_mongo_db()["student_profiles"].find_one({"_id": 1})
    print("Студент 1: оцінок", len(doc["grades"]), "| досягнень", len(doc["achievements"]),
          "| середній бал", doc["stats"]["avg_grade"])
