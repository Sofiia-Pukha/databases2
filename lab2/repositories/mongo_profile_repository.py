from datetime import date, datetime

from pymongo import WriteConcern


def to_datetime(d):
    # mongo зберігає тільки datetime
    if isinstance(d, date) and not isinstance(d, datetime):
        return datetime(d.year, d.month, d.day)
    return d


class MongoProfileRepository:
    name = "MongoDB"

    def __init__(self, db):
        # j=True - чекаємо запису в журнал, як commit у postgres
        self.col = db.get_collection("student_profiles",
                                     write_concern=WriteConcern(w=1, j=True))

    def get_profile(self, student_id):
        return self.col.find_one({"_id": student_id})

    def get_group_profiles(self, group_id):
        return list(self.col.find({"group.id": group_id}).sort("_id", 1))

    def avg_by_subject(self):
        return list(self.col.aggregate([
            {"$unwind": "$grades"},
            {"$group": {"_id": "$grades.subject_id",
                        "subject": {"$first": "$grades.subject"},
                        "avg_grade": {"$avg": "$grades.grade"},
                        "cnt": {"$sum": 1}}},
            {"$sort": {"_id": 1}},
        ], allowDiskUse=True))

    def find_olympiad_winners(self, level, place):
        return list(self.col.find(
            {"achievements": {"$elemMatch": {"type": "olympiad", "level": level, "place": place}}},
            {"first_name": 1, "last_name": 1, "group.name": 1},
        ).sort("_id", 1))

    def faculty_top(self, faculty_id, limit=20):
        return list(self.col.find(
            {"group.faculty.id": faculty_id},
            {"last_name": 1, "group.name": 1, "stats.avg_grade": 1},
        ).sort([("stats.avg_grade", -1), ("_id", 1)]).limit(limit))

    def add_grade(self, student_id, subject_id, semester_id, grade, grade_date,
                  subject_name="", credits=0, semester_name=""):
        item = {"subject_id": subject_id, "subject": subject_name, "credits": credits,
                "semester_id": semester_id, "semester": semester_name,
                "grade": grade, "date": to_datetime(grade_date)}
        # додаємо оцінку і одразу перераховуємо середній бал
        self.col.update_one({"_id": student_id}, [
            {"$set": {"grades": {"$concatArrays": ["$grades", [item]]}}},
            {"$set": {"stats.avg_grade": {"$round": [{"$avg": "$grades.grade"}, 2]},
                      "stats.grades_count": {"$size": "$grades"},
                      "updated_at": "$$NOW"}},
        ])

    def rename_subject(self, subject_id, new_name):
        result = self.col.update_many(
            {"grades.subject_id": subject_id},
            {"$set": {"grades.$[g].subject": new_name}},
            array_filters=[{"g.subject_id": subject_id}],
        )
        return result.modified_count

    def add_achievement(self, student_id, achievement):
        achievement["date"] = to_datetime(achievement["date"])
        self.col.update_one({"_id": student_id}, {"$push": {"achievements": achievement}})
