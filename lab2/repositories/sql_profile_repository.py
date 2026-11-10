class SqlProfileRepository:
    name = "SQL (3 запити)"

    def __init__(self, cursor):
        self.cursor = cursor

    def get_profile(self, student_id):
        self.cursor.execute("SELECT * FROM v_student_card WHERE id = %s", (student_id,))
        card = self.cursor.fetchone()
        if card is None:
            return None
        self.cursor.execute(
            "SELECT * FROM v_student_grades WHERE student_id = %s ORDER BY grade_id",
            (student_id,),
        )
        grades = self.cursor.fetchall()
        self.cursor.execute(
            "SELECT * FROM v_student_achievements WHERE student_id = %s ORDER BY achieved_at",
            (student_id,),
        )
        achievements = self.cursor.fetchall()
        return make_profile(card, grades, achievements)

    def get_group_profiles(self, group_id):
        self.cursor.execute(
            "SELECT * FROM v_student_card WHERE group_id = %s ORDER BY id", (group_id,)
        )
        cards = self.cursor.fetchall()
        ids = [c["id"] for c in cards]

        self.cursor.execute(
            "SELECT * FROM v_student_grades WHERE student_id = ANY(%s) ORDER BY grade_id",
            (ids,),
        )
        grades = {}
        for g in self.cursor.fetchall():
            grades.setdefault(g["student_id"], []).append(g)

        self.cursor.execute(
            "SELECT * FROM v_student_achievements WHERE student_id = ANY(%s) ORDER BY achieved_at",
            (ids,),
        )
        achievements = {}
        for a in self.cursor.fetchall():
            achievements.setdefault(a["student_id"], []).append(a)

        return [make_profile(c, grades.get(c["id"], []), achievements.get(c["id"], []))
                for c in cards]

    def avg_by_subject(self):
        self.cursor.execute(
            "SELECT sub.id AS subject_id, sub.name AS subject, "
            "ROUND(AVG(x.grade), 2) AS avg_grade, COUNT(*) AS cnt "
            "FROM grades x JOIN subjects sub ON sub.id = x.subject_id "
            "GROUP BY sub.id ORDER BY sub.id"
        )
        return self.cursor.fetchall()

    def find_olympiad_winners(self, level, place):
        self.cursor.execute(
            "SELECT s.id AS student_id, s.first_name, s.last_name, g.name AS group_name, a.title "
            "FROM olympiad_details od "
            "JOIN achievements a ON a.id = od.achievement_id AND a.is_deleted = FALSE "
            "JOIN students s ON s.id = a.student_id AND s.is_deleted = FALSE "
            "JOIN groups g ON g.id = s.group_id "
            "WHERE od.level = %s AND od.place = %s ORDER BY s.id",
            (level, place),
        )
        return self.cursor.fetchall()

    def faculty_top(self, faculty_id, limit=20):
        self.cursor.execute("SELECT * FROM fn_faculty_top(%s, %s)", (faculty_id, limit))
        return self.cursor.fetchall()

    def add_grade(self, student_id, subject_id, semester_id, grade, grade_date, **kwargs):
        self.cursor.execute(
            "CALL sp_add_grade(%s, %s, %s, %s, %s, NULL)",
            (student_id, subject_id, semester_id, grade, grade_date),
        )
        return self.cursor.fetchone()["p_id"]

    def rename_subject(self, subject_id, new_name):
        self.cursor.execute("CALL sp_rename_subject(%s, %s)", (subject_id, new_name))


# той самий профіль, але одним запитом через v_student_profile
class SqlOneQueryProfileRepository(SqlProfileRepository):
    name = "SQL (1 запит)"

    def get_profile(self, student_id):
        self.cursor.execute("SELECT doc FROM v_student_profile WHERE id = %s", (student_id,))
        row = self.cursor.fetchone()
        return row["doc"] if row else None

    def get_group_profiles(self, group_id):
        self.cursor.execute(
            "SELECT p.doc FROM v_student_profile p JOIN students s ON s.id = p.id "
            "WHERE s.group_id = %s ORDER BY p.id",
            (group_id,),
        )
        return [r["doc"] for r in self.cursor.fetchall()]


def make_profile(card, grades, achievements):
    items = []
    for g in grades:
        items.append({
            "grade_id": g["grade_id"], "subject_id": g["subject_id"], "subject": g["subject"],
            "credits": g["credits"], "semester_id": g["semester_id"], "semester": g["semester"],
            "grade": g["grade"], "date": g["grade_date"],
        })

    ach = []
    for a in achievements:
        item = {"achievement_id": a["achievement_id"], "type": a["type"],
                "title": a["title"], "date": a["achieved_at"]}
        for key in ("level", "place", "provider", "hours", "url", "journal", "year", "coauthors"):
            if a[key] is not None:
                item[key] = a[key]
        ach.append(item)

    avg = round(sum(i["grade"] for i in items) / len(items), 2) if items else 0

    return {
        "_id": card["id"],
        "first_name": card["first_name"],
        "last_name": card["last_name"],
        "email": card["email"],
        "birth_date": card["birth_date"],
        "group": {
            "id": card["group_id"],
            "name": card["group_name"],
            "course_year": card["course_year"],
            "specialty": {"id": card["specialty_id"], "name": card["specialty_name"]},
            "faculty": {"id": card["faculty_id"], "name": card["faculty_name"]},
        },
        "grades": items,
        "stats": {"avg_grade": avg, "grades_count": len(items)},
        "achievements": ach,
        "updated_at": card["updated_at"],
    }
