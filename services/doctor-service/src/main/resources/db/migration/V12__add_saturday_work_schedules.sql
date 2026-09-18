WITH weekday_template AS (
    SELECT DISTINCT ON (doctor_id)
           doctor_id,
           start_time,
           end_time,
           slot_minutes
    FROM work_schedules
    WHERE weekday BETWEEN 1 AND 5
    ORDER BY doctor_id, weekday, start_time
)
INSERT INTO work_schedules (id, doctor_id, weekday, start_time, end_time, slot_minutes)
SELECT gen_random_uuid(), template.doctor_id, 6,
       template.start_time, template.end_time, template.slot_minutes
FROM weekday_template template
WHERE NOT EXISTS (
    SELECT 1
    FROM work_schedules saturday
    WHERE saturday.doctor_id = template.doctor_id
      AND saturday.weekday = 6
);
