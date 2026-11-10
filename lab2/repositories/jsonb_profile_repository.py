import json


class JsonbProfileRepository:
    name = "PostgreSQL JSONB"

    def __init__(self, cursor):
        self.cursor = cursor

    def get_profile(self, student_id):
        self.cursor.execute("SELECT doc FROM student_profiles_jsonb WHERE id = %s", (student_id,))
        row = self.cursor.fetchone()
        return row["doc"] if row else None

    def get_group_profiles(self, group_id):
        self.cursor.execute(
            "SELECT doc FROM student_profiles_jsonb "
            "WHERE (doc #>> '{group,id}')::INT = %s ORDER BY id",
            (group_id,),
        )
        return [r["doc"] for r in self.cursor.fetchall()]

    def avg_by_subject(self):
        self.cursor.execute(
            "SELECT (e->>'subject_id')::INT AS subject_id, MIN(e->>'subject') AS subject, "
            "ROUND(AVG((e->>'grade')::INT), 2) AS avg_grade, COUNT(*) AS cnt "
            "FROM student_profiles_jsonb p, jsonb_array_elements(p.doc->'grades') e "
            "GROUP BY 1 ORDER BY 1"
        )
        return self.cursor.fetchall()

    def find_olympiad_winners(self, level, place):
        pattern = {"achievements": [{"type": "olympiad", "level": level, "place": place}]}
        self.cursor.execute(
            "SELECT id AS student_id, doc->>'first_name' AS first_name, "
            "doc->>'last_name' AS last_name, doc #>> '{group,name}' AS group_name "
            "FROM student_profiles_jsonb WHERE doc @> %s::jsonb ORDER BY id",
            (json.dumps(pattern),),
        )
        return self.cursor.fetchall()

    def faculty_top(self, faculty_id, limit=20):
        self.cursor.execute(
            "SELECT id AS student_id, doc->>'last_name' AS last_name, "
            "doc #>> '{group,name}' AS group_name, "
            "(doc #>> '{stats,avg_grade}')::NUMERIC AS avg_grade "
            "FROM student_profiles_jsonb "
            "WHERE (doc #>> '{group,faculty,id}')::INT = %s "
            "ORDER BY (doc #>> '{stats,avg_grade}')::NUMERIC DESC, id LIMIT %s",
            (faculty_id, limit),
        )
        return self.cursor.fetchall()

    def add_grade(self, student_id, subject_id, semester_id, grade, grade_date,
                  subject_name="", credits=0, semester_name=""):
        item = {"subject_id": subject_id, "subject": subject_name, "credits": credits,
                "semester_id": semester_id, "semester": semester_name,
                "grade": grade, "date": grade_date.isoformat()}
        self.cursor.execute("CALL sp_jsonb_add_grade(%s, %s::jsonb)",
                            (student_id, json.dumps(item)))

    def rename_subject(self, subject_id, new_name):
        self.cursor.execute("CALL sp_jsonb_rename_subject(%s, %s)", (subject_id, new_name))
