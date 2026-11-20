CREATE TABLE clinic_workdays (
    weekday integer PRIMARY KEY CHECK (weekday BETWEEN 1 AND 7),
    open boolean NOT NULL,
    start_time time NOT NULL,
    end_time time NOT NULL,
    CHECK (end_time - start_time >= interval '30 minutes')
);
