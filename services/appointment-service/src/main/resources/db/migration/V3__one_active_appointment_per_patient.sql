create unique index if not exists uq_patient_active_appointment
    on appointment.appointments(patient_identity_id)
    where status in ('PENDING','ASSIGNED','CONFIRMED','IN_PROGRESS');
