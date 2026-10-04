CREATE TABLE clinic_service_doctors (
    service_id UUID NOT NULL REFERENCES clinic_services(id) ON DELETE CASCADE,
    doctor_id UUID NOT NULL REFERENCES doctors(id) ON DELETE CASCADE,
    PRIMARY KEY (service_id, doctor_id)
);

INSERT INTO clinic_service_doctors (service_id, doctor_id)
SELECT service.id, doctor.id
FROM clinic_services service
JOIN doctors doctor
  ON upper(trim(doctor.specialty_code)) = upper(trim(service.specialty_code));

CREATE INDEX ix_clinic_service_doctors_doctor
    ON clinic_service_doctors (doctor_id, service_id);
