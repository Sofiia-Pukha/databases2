-- схема для лабораторної 2 (окремо від public з лаби 1)
DROP SCHEMA IF EXISTS lab2 CASCADE;
CREATE SCHEMA lab2;
SET search_path TO lab2;

-- таблиці як у лабі 1
CREATE TABLE faculties (
    id   SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE
);

CREATE TABLE specialties (
    id         SERIAL PRIMARY KEY,
    name       VARCHAR(100) NOT NULL,
    faculty_id INT NOT NULL REFERENCES faculties(id)
);

CREATE TABLE groups (
    id           SERIAL PRIMARY KEY,
    name         VARCHAR(20) NOT NULL UNIQUE,
    specialty_id INT NOT NULL REFERENCES specialties(id),
    course_year  INT NOT NULL CHECK (course_year BETWEEN 1 AND 6),
    is_deleted   BOOLEAN NOT NULL DEFAULT FALSE,
    deleted_at   TIMESTAMP
);

CREATE TABLE students (
    id         SERIAL PRIMARY KEY,
    first_name VARCHAR(50) NOT NULL,
    last_name  VARCHAR(50) NOT NULL,
    email      VARCHAR(100) UNIQUE,
    birth_date DATE,
    group_id   INT NOT NULL REFERENCES groups(id),
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    deleted_at TIMESTAMP,
    updated_at TIMESTAMP,
    updated_by INT
);

CREATE TABLE subjects (
    id         SERIAL PRIMARY KEY,
    name       VARCHAR(100) NOT NULL UNIQUE,
    credits    INT NOT NULL CHECK (credits > 0),
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    deleted_at TIMESTAMP
);

CREATE TABLE semesters (
    id         SERIAL PRIMARY KEY,
    name       VARCHAR(50) NOT NULL UNIQUE,
    start_date DATE NOT NULL,
    end_date   DATE NOT NULL,
    CHECK (end_date > start_date)
);

CREATE TABLE grades (
    id          SERIAL PRIMARY KEY,
    student_id  INT NOT NULL REFERENCES students(id),
    subject_id  INT NOT NULL REFERENCES subjects(id),
    semester_id INT NOT NULL REFERENCES semesters(id),
    grade       INT NOT NULL CHECK (grade BETWEEN 0 AND 100),
    grade_date  DATE NOT NULL,
    updated_at  TIMESTAMP,
    updated_by  INT
);

-- портфоліо досягнень: спільні поля + окрема таблиця для кожного типу
CREATE TABLE achievements (
    id          SERIAL PRIMARY KEY,
    student_id  INT NOT NULL REFERENCES students(id),
    type        VARCHAR(20) NOT NULL
                CHECK (type IN ('olympiad', 'certificate', 'publication')),
    title       VARCHAR(200) NOT NULL,
    achieved_at DATE NOT NULL,
    is_deleted  BOOLEAN NOT NULL DEFAULT FALSE,
    deleted_at  TIMESTAMP,
    updated_at  TIMESTAMP DEFAULT NOW()
);

CREATE TABLE olympiad_details (
    achievement_id INT PRIMARY KEY REFERENCES achievements(id) ON DELETE CASCADE,
    level          VARCHAR(20) NOT NULL
                   CHECK (level IN ('university', 'city', 'national', 'international')),
    place          INT NOT NULL CHECK (place BETWEEN 1 AND 10)
);

CREATE TABLE certificate_details (
    achievement_id INT PRIMARY KEY REFERENCES achievements(id) ON DELETE CASCADE,
    provider       VARCHAR(100) NOT NULL,
    hours          INT NOT NULL CHECK (hours > 0),
    url            VARCHAR(300)
);

CREATE TABLE publication_details (
    achievement_id INT PRIMARY KEY REFERENCES achievements(id) ON DELETE CASCADE,
    journal        VARCHAR(200) NOT NULL,
    year           INT NOT NULL
);

CREATE TABLE publication_coauthors (
    achievement_id INT NOT NULL REFERENCES publication_details(achievement_id) ON DELETE CASCADE,
    position       INT NOT NULL,
    coauthor_name  VARCHAR(100) NOT NULL,
    PRIMARY KEY (achievement_id, position)
);

-- той самий профіль, що в MongoDB, але в jsonb
CREATE TABLE student_profiles_jsonb (
    id  INT PRIMARY KEY,
    doc JSONB NOT NULL
);
