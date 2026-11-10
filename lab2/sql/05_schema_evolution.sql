-- новий тип досягнення "hackathon" у SQL
-- (у MongoDB достатньо просто вставити документ з новими полями)
BEGIN;
SET search_path TO lab2;

ALTER TABLE achievements DROP CONSTRAINT achievements_type_check;
ALTER TABLE achievements ADD CONSTRAINT achievements_type_check
    CHECK (type IN ('olympiad', 'certificate', 'publication', 'hackathon'));

CREATE TABLE hackathon_details (
    achievement_id INT PRIMARY KEY REFERENCES achievements(id) ON DELETE CASCADE,
    team           VARCHAR(100) NOT NULL,
    prize_uah      INT
);

CREATE TABLE hackathon_stack (
    achievement_id INT REFERENCES hackathon_details(achievement_id) ON DELETE CASCADE,
    technology     VARCHAR(50),
    PRIMARY KEY (achievement_id, technology)
);

WITH a AS (
    INSERT INTO achievements (student_id, type, title, achieved_at)
    VALUES (42, 'hackathon', 'Lviv IT Hackathon 2026', '2026-10-12')
    RETURNING id
), h AS (
    INSERT INTO hackathon_details SELECT id, 'NullPointers', 15000 FROM a
    RETURNING achievement_id
)
INSERT INTO hackathon_stack
SELECT achievement_id, unnest(ARRAY['Python', 'MongoDB', 'Redis']) FROM h;

-- + треба ще змінити v_student_achievements і v_student_profile

SELECT a.id, a.type, a.title, h.team, h.prize_uah,
       (SELECT array_agg(technology) FROM hackathon_stack s
        WHERE s.achievement_id = a.id) AS stack
FROM achievements a
JOIN hackathon_details h ON h.achievement_id = a.id;

ROLLBACK;
