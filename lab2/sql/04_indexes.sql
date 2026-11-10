SET search_path TO lab2;

-- b-tree
CREATE INDEX IF NOT EXISTS idx_l2_grades_student       ON grades (student_id);
CREATE INDEX IF NOT EXISTS idx_l2_grades_subject       ON grades (subject_id);
CREATE INDEX IF NOT EXISTS idx_l2_achievements_student ON achievements (student_id);
CREATE INDEX IF NOT EXISTS idx_l2_olympiad_level_place ON olympiad_details (level, place);
CREATE INDEX IF NOT EXISTS idx_l2_groups_specialty     ON groups (specialty_id);

-- частковий індекс
CREATE INDEX IF NOT EXISTS idx_l2_students_group
    ON students (group_id) WHERE is_deleted = FALSE;

-- gin для пошуку всередині jsonb
CREATE INDEX IF NOT EXISTS idx_l2_profiles_doc_gin
    ON student_profiles_jsonb USING gin (doc jsonb_path_ops);

-- індекси по виразах jsonb
CREATE INDEX IF NOT EXISTS idx_l2_profiles_group
    ON student_profiles_jsonb (((doc #>> '{group,id}')::INT));

CREATE INDEX IF NOT EXISTS idx_l2_profiles_faculty_avg
    ON student_profiles_jsonb (((doc #>> '{group,faculty,id}')::INT),
                               ((doc #>> '{stats,avg_grade}')::NUMERIC) DESC, id);

ANALYZE;
