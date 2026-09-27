package com.dermai.patient;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import java.time.Instant;
import java.util.*;

public interface AiAssessmentRepository extends JpaRepository<AiAssessment, UUID> {
  List<AiAssessment> findByPatientIdentityIdAndDeletedAtIsNullOrderByCreatedAtDesc(UUID patientIdentityId);
  Optional<AiAssessment> findByIdAndPatientIdentityIdAndDeletedAtIsNull(UUID id, UUID patientIdentityId);
  Optional<AiAssessment> findFirstByAppointmentIdAndSharedWithDoctorTrueAndDeletedAtIsNullOrderByCreatedAtDesc(UUID appointmentId);

  @Modifying(clearAutomatically = true)
  @Query("""
      update AiAssessment a
      set a.imageBytes = null, a.imageContentType = null
      where a.imageBytes is not null
        and a.imageRetentionUntil is not null
        and a.imageRetentionUntil <= :now
      """)
  int purgeExpiredImages(@Param("now") Instant now);
}
