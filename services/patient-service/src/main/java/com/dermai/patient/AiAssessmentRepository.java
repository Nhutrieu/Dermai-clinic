package com.dermai.patient;

import org.springframework.data.jpa.repository.JpaRepository;
import java.util.*;

public interface AiAssessmentRepository extends JpaRepository<AiAssessment, UUID> {
  List<AiAssessment> findByPatientIdentityIdOrderByCreatedAtDesc(UUID patientIdentityId);
  Optional<AiAssessment> findByIdAndPatientIdentityId(UUID id, UUID patientIdentityId);
  Optional<AiAssessment> findFirstByAppointmentIdAndSharedWithDoctorTrueOrderByCreatedAtDesc(UUID appointmentId);
}
