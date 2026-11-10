-- генерація тестових даних, напр. CALL lab2.sp_generate_data(100000, 30);
SET search_path TO lab2;

CREATE OR REPLACE PROCEDURE sp_generate_data(p_students INT, p_grades_per_student INT DEFAULT 30)
LANGUAGE plpgsql SET search_path = lab2 AS $$
DECLARE
    v_groups INT := CEIL(p_students / 25.0);  -- 25 студентів у групі
BEGIN
    PERFORM setseed(0.42);

    TRUNCATE publication_coauthors, publication_details, certificate_details,
             olympiad_details, achievements, grades, students, groups,
             specialties, faculties, subjects, semesters, student_profiles_jsonb
             RESTART IDENTITY CASCADE;

    -- довідники
    INSERT INTO faculties (name) VALUES
        ('Факультет інформаційних технологій'), ('Економічний факультет'),
        ('Юридичний факультет'), ('Факультет прикладної математики'),
        ('Гуманітарний факультет');

    INSERT INTO specialties (name, faculty_id)
    SELECT (ARRAY['Комп''ютерні науки','Інженерія ПЗ','Кібербезпека',
                  'Економіка','Фінанси','Маркетинг',
                  'Право','Міжнародне право','Правоохоронна діяльність',
                  'Прикладна математика','Статистика','Системний аналіз',
                  'Філологія','Історія','Психологія'])[i],
           1 + (i - 1) / 3
    FROM generate_series(1, 15) AS i;

    INSERT INTO groups (name, specialty_id, course_year)
    SELECT 'G-' || LPAD(i::TEXT, 5, '0'), 1 + (i % 15), 1 + (i % 4)
    FROM generate_series(1, v_groups) AS i;

    INSERT INTO subjects (name, credits)
    SELECT (ARRAY['Програмування','Бази даних','Вища математика','Англійська мова',
                  'Алгоритми','Мікроекономіка','Теорія права','Фізика',
                  'Операційні системи','Комп''ютерні мережі','Статистика',
                  'Філософія','Історія України','Дискретна математика',
                  'Веб-технології'])[1 + (i - 1) % 15] || ' ' || (1 + (i - 1) / 15),
           3 + (i % 4)
    FROM generate_series(1, 60) AS i;

    INSERT INTO semesters (name, start_date, end_date)
    SELECT (2022 + (i - 1) / 2) || '/' || (2023 + (i - 1) / 2)
               || CASE WHEN i % 2 = 1 THEN ' осінь' ELSE ' весна' END,
           MAKE_DATE(2022 + (i - 1) / 2 + (CASE WHEN i % 2 = 1 THEN 0 ELSE 1 END),
                     CASE WHEN i % 2 = 1 THEN 9 ELSE 2 END, 1),
           MAKE_DATE(2022 + (i - 1) / 2 + 1,
                     CASE WHEN i % 2 = 1 THEN 1 ELSE 6 END, 28)
    FROM generate_series(1, 8) AS i;

    -- студенти
    INSERT INTO students (first_name, last_name, email, birth_date, group_id, updated_at, updated_by)
    SELECT (ARRAY['Олександр','Андрій','Марія','Олена','Іван','Наталія','Дмитро',
                  'Софія','Богдан','Анна','Тарас','Юлія','Максим','Ірина'])[1 + (i % 14)],
           (ARRAY['Шевченко','Коваленко','Бондаренко','Мельник','Ткаченко','Кравченко',
                  'Олійник','Мороз','Лисенко','Гриценко','Савченко','Петренко',
                  'Литвиненко','Романюк','Гаврилюк','Вишневська'])[1 + (i % 16)],
           'st' || i || '@univ.ua',
           DATE '2002-01-01' + (i % 2000),
           1 + (i - 1) % v_groups,
           NOW(), 1
    FROM generate_series(1, p_students) AS i;

    -- оцінки
    INSERT INTO grades (student_id, subject_id, semester_id, grade, grade_date, updated_at, updated_by)
    SELECT s.id,
           1 + ((s.id * 7 + k * 11) % 60),
           1 + (k - 1) % 8,
           50 + FLOOR(RANDOM() * 51)::INT,
           DATE '2023-01-10' + ((k - 1) % 8) * 180 + (k % 10),
           NOW(), 1
    FROM students s
    CROSS JOIN generate_series(1, p_grades_per_student) AS k;

    -- досягнення (0-3 на студента)
    INSERT INTO achievements (student_id, type, title, achieved_at)
    SELECT s.id, t.type,
           CASE t.type
               WHEN 'olympiad'    THEN 'Олімпіада з дисципліни "' || sub.name || '"'
               WHEN 'certificate' THEN 'Онлайн-курс "' || sub.name || '"'
               ELSE 'Стаття: дослідження в галузі "' || sub.name || '"'
           END,
           DATE '2022-10-01' + FLOOR(RANDOM() * 1400)::INT
    FROM students s
    CROSS JOIN LATERAL generate_series(1, (s.id * 7) % 4) AS n
    CROSS JOIN LATERAL (SELECT (ARRAY['olympiad','certificate','publication'])
                               [1 + ((s.id + n) % 3)] AS type) t
    JOIN subjects sub ON sub.id = 1 + ((s.id + n * 17) % 60);

    INSERT INTO olympiad_details (achievement_id, level, place)
    SELECT a.id,
           CASE WHEN a.id % 50 = 0 THEN 'international'
                WHEN a.id % 10 = 1 THEN 'national'
                WHEN a.id % 3 = 0  THEN 'city'
                ELSE 'university' END,
           1 + FLOOR(RANDOM() * 10)::INT
    FROM achievements a
    WHERE a.type = 'olympiad';

    INSERT INTO certificate_details (achievement_id, provider, hours, url)
    SELECT a.id,
           (ARRAY['Coursera','Prometheus','Cisco NetAcad','Google','Microsoft Learn'])
               [1 + (a.id % 5)],
           10 + (a.id % 12) * 10,
           'https://cert.example.com/' || md5(a.id::TEXT)
    FROM achievements a
    WHERE a.type = 'certificate';

    INSERT INTO publication_details (achievement_id, journal, year)
    SELECT a.id,
           (ARRAY['Вісник університету','Наукові записки','Проблеми програмування',
                  'Economics and Law','IEEE Student Conference'])[1 + (a.id % 5)],
           EXTRACT(YEAR FROM a.achieved_at)::INT
    FROM achievements a
    WHERE a.type = 'publication';

    INSERT INTO publication_coauthors (achievement_id, position, coauthor_name)
    SELECT p.achievement_id, k,
           (ARRAY['Мельник І.','Ковальчук О.','Шевчук П.','Бойко Н.','Лисенко В.'])
               [1 + ((p.achievement_id + k) % 5)]
    FROM publication_details p
    CROSS JOIN LATERAL generate_series(1, p.achievement_id % 4) AS k;

    -- jsonb-профілі
    INSERT INTO student_profiles_jsonb (id, doc)
    SELECT id, doc FROM v_student_profile;
END;
$$;
