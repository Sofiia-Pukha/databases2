SET search_path TO lab2;

-- профіль студента одним документом (з 12 таблиць)
CREATE OR REPLACE VIEW v_student_profile AS
SELECT s.id,
       jsonb_build_object(
           '_id',        s.id,
           'first_name', s.first_name,
           'last_name',  s.last_name,
           'email',      s.email,
           'birth_date', s.birth_date,
           'group', jsonb_build_object(
               'id',          g.id,
               'name',        g.name,
               'course_year', g.course_year,
               'specialty',   jsonb_build_object('id', sp.id, 'name', sp.name),
               'faculty',     jsonb_build_object('id', f.id,  'name', f.name)),
           'grades',       COALESCE(gr.items, '[]'::jsonb),
           'stats',        jsonb_build_object('avg_grade',    COALESCE(gr.avg_grade, 0),
                                              'grades_count', COALESCE(gr.cnt, 0)),
           'achievements', COALESCE(ac.items, '[]'::jsonb),
           'updated_at',   s.updated_at
       ) AS doc
FROM students s
JOIN groups g       ON g.id  = s.group_id
JOIN specialties sp ON sp.id = g.specialty_id
JOIN faculties f    ON f.id  = sp.faculty_id
LEFT JOIN LATERAL (
    SELECT jsonb_agg(jsonb_build_object(
               'grade_id',    x.id,
               'subject_id',  sub.id,
               'subject',     sub.name,
               'credits',     sub.credits,
               'semester_id', sem.id,
               'semester',    sem.name,
               'grade',       x.grade,
               'date',        x.grade_date) ORDER BY x.id) AS items,
           ROUND(AVG(x.grade), 2) AS avg_grade,
           COUNT(*) AS cnt
    FROM grades x
    JOIN subjects  sub ON sub.id = x.subject_id
    JOIN semesters sem ON sem.id = x.semester_id
    WHERE x.student_id = s.id
) gr ON TRUE
LEFT JOIN LATERAL (
    SELECT jsonb_agg(jsonb_strip_nulls(jsonb_build_object(
               'achievement_id', a.id,
               'type',      a.type,
               'title',     a.title,
               'date',      a.achieved_at,
               'level',     od.level,
               'place',     od.place,
               'provider',  cd.provider,
               'hours',     cd.hours,
               'url',       cd.url,
               'journal',   pd.journal,
               'year',      pd.year,
               'coauthors', (SELECT jsonb_agg(pc.coauthor_name ORDER BY pc.position)
                             FROM publication_coauthors pc
                             WHERE pc.achievement_id = a.id)))
               ORDER BY a.achieved_at) AS items
    FROM achievements a
    LEFT JOIN olympiad_details    od ON od.achievement_id = a.id
    LEFT JOIN certificate_details cd ON cd.achievement_id = a.id
    LEFT JOIN publication_details pd ON pd.achievement_id = a.id
    WHERE a.student_id = s.id AND a.is_deleted = FALSE
) ac ON TRUE
WHERE s.is_deleted = FALSE;

-- картка студента
CREATE OR REPLACE VIEW v_student_card AS
SELECT s.id, s.first_name, s.last_name, s.email, s.birth_date, s.updated_at,
       g.id AS group_id, g.name AS group_name, g.course_year,
       sp.id AS specialty_id, sp.name AS specialty_name,
       f.id  AS faculty_id,   f.name  AS faculty_name
FROM students s
JOIN groups g       ON g.id  = s.group_id
JOIN specialties sp ON sp.id = g.specialty_id
JOIN faculties f    ON f.id  = sp.faculty_id
WHERE s.is_deleted = FALSE;

-- оцінки з назвами дисциплін і семестрів
CREATE OR REPLACE VIEW v_student_grades AS
SELECT x.id AS grade_id, x.student_id,
       sub.id AS subject_id, sub.name AS subject, sub.credits,
       sem.id AS semester_id, sem.name AS semester,
       x.grade, x.grade_date
FROM grades x
JOIN subjects  sub ON sub.id = x.subject_id
JOIN semesters sem ON sem.id = x.semester_id;

-- досягнення з деталями
CREATE OR REPLACE VIEW v_student_achievements AS
SELECT a.id AS achievement_id, a.student_id, a.type, a.title, a.achieved_at,
       od.level, od.place,
       cd.provider, cd.hours, cd.url,
       pd.journal, pd.year,
       (SELECT array_agg(pc.coauthor_name ORDER BY pc.position)
        FROM publication_coauthors pc WHERE pc.achievement_id = a.id) AS coauthors
FROM achievements a
LEFT JOIN olympiad_details    od ON od.achievement_id = a.id
LEFT JOIN certificate_details cd ON cd.achievement_id = a.id
LEFT JOIN publication_details pd ON pd.achievement_id = a.id
WHERE a.is_deleted = FALSE;

-- додати оцінку
CREATE OR REPLACE PROCEDURE sp_add_grade(
    p_student_id  INT,
    p_subject_id  INT,
    p_semester_id INT,
    p_grade       INT,
    p_grade_date  DATE,
    INOUT p_id    INT
)
LANGUAGE plpgsql SET search_path = lab2 AS $$
BEGIN
    INSERT INTO grades (student_id, subject_id, semester_id, grade, grade_date, updated_at)
    VALUES (p_student_id, p_subject_id, p_semester_id, p_grade, p_grade_date, NOW())
    RETURNING id INTO p_id;
END;
$$;

-- перейменувати дисципліну
CREATE OR REPLACE PROCEDURE sp_rename_subject(p_subject_id INT, p_name VARCHAR)
LANGUAGE plpgsql SET search_path = lab2 AS $$
BEGIN
    UPDATE subjects SET name = p_name WHERE id = p_subject_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Дисципліну з id % не знайдено', p_subject_id;
    END IF;
END;
$$;

-- додати оцінку в jsonb-профіль і перерахувати середній бал
CREATE OR REPLACE PROCEDURE sp_jsonb_add_grade(p_student_id INT, p_grade JSONB)
LANGUAGE plpgsql SET search_path = lab2 AS $$
BEGIN
    UPDATE student_profiles_jsonb p
    SET doc = jsonb_set(
                  jsonb_set(p.doc, '{grades}', (p.doc->'grades') || jsonb_build_array(p_grade)),
                  '{stats}',
                  (SELECT jsonb_build_object('avg_grade', ROUND(AVG((e->>'grade')::INT), 2),
                                             'grades_count', COUNT(*))
                   FROM jsonb_array_elements((p.doc->'grades') || jsonb_build_array(p_grade)) e))
    WHERE p.id = p_student_id;
END;
$$;

-- перейменувати дисципліну в усіх jsonb-профілях
CREATE OR REPLACE PROCEDURE sp_jsonb_rename_subject(p_subject_id INT, p_name VARCHAR)
LANGUAGE plpgsql SET search_path = lab2 AS $$
BEGIN
    UPDATE student_profiles_jsonb p
    SET doc = jsonb_set(p.doc, '{grades}',
              (SELECT jsonb_agg(CASE WHEN (e->>'subject_id')::INT = p_subject_id
                                     THEN jsonb_set(e, '{subject}', to_jsonb(p_name))
                                     ELSE e END)
               FROM jsonb_array_elements(p.doc->'grades') e))
    WHERE p.doc->'grades' @> jsonb_build_array(jsonb_build_object('subject_id', p_subject_id));
END;
$$;

-- топ студентів факультету за середнім балом
CREATE OR REPLACE FUNCTION fn_faculty_top(p_faculty_id INT, p_limit INT DEFAULT 20)
RETURNS TABLE (student_id INT, full_name TEXT, group_name VARCHAR, avg_grade NUMERIC)
LANGUAGE sql STABLE SET search_path = lab2 AS $$
    SELECT s.id, s.last_name || ' ' || s.first_name, g.name, ROUND(AVG(x.grade), 2)
    FROM students s
    JOIN groups g       ON g.id  = s.group_id
    JOIN specialties sp ON sp.id = g.specialty_id
    JOIN grades x       ON x.student_id = s.id
    WHERE sp.faculty_id = p_faculty_id AND s.is_deleted = FALSE
    GROUP BY s.id, g.name
    ORDER BY 4 DESC, s.id
    LIMIT p_limit;
$$;
