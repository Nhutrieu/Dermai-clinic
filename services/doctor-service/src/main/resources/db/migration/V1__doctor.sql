CREATE TABLE doctors(id uuid PRIMARY KEY,identity_id uuid UNIQUE,full_name varchar(160) NOT NULL,specialty_code varchar(80) NOT NULL,experience_years int NOT NULL CHECK(experience_years>=0),certificate_no varchar(100),active boolean NOT NULL DEFAULT true);
CREATE INDEX ix_doctor_specialty ON doctors(specialty_code) WHERE active;
CREATE TABLE work_schedules(id uuid PRIMARY KEY,doctor_id uuid NOT NULL REFERENCES doctors(id) ON DELETE CASCADE,weekday smallint NOT NULL CHECK(weekday BETWEEN 1 AND 7),start_time time NOT NULL,end_time time NOT NULL,slot_minutes int NOT NULL CHECK(slot_minutes BETWEEN 10 AND 120),CHECK(start_time<end_time),UNIQUE(doctor_id,weekday,start_time,end_time));
CREATE TABLE leave_periods(id uuid PRIMARY KEY,doctor_id uuid NOT NULL REFERENCES doctors(id) ON DELETE CASCADE,start_at timestamptz NOT NULL,end_at timestamptz NOT NULL,reason varchar(250),CHECK(start_at<end_at));
CREATE INDEX ix_leave_doctor_time ON leave_periods(doctor_id,start_at,end_at);
