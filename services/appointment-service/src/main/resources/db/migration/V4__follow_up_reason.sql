alter table appointment.appointments
    add column if not exists follow_up_reason varchar(500),
    add column if not exists follow_up_not_before timestamptz;
