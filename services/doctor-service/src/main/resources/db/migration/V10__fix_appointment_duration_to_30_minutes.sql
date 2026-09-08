UPDATE work_schedules
SET slot_minutes = 30
WHERE slot_minutes <> 30;

UPDATE slot_duration_policies
SET slot_minutes = 30
WHERE slot_minutes <> 30;
