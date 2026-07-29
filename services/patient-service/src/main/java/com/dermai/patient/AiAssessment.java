package com.dermai.patient;

import jakarta.persistence.*;
import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name = "ai_assessments")
public class AiAssessment {
  @Id public UUID id;
  @Column(name = "patient_id", nullable = false) public UUID patientId;
  @Column(name = "patient_identity_id", nullable = false) public UUID patientIdentityId;
  @Column(name = "predicted_label", nullable = false, length = 80) public String predictedLabel;
  @Column(nullable = false) public double confidence;
  @Column(name = "top3_json", nullable = false, columnDefinition = "text") public String top3Json;
  @Column(nullable = false) public boolean uncertain;
  @Column(name = "model_version", nullable = false, length = 120) public String modelVersion;
  @Column(name = "shared_with_doctor", nullable = false) public boolean sharedWithDoctor;
  @Column(name = "appointment_id") public UUID appointmentId;
  @Column(name = "image_content_type", length = 80) public String imageContentType;
  @Column(name = "image_bytes", columnDefinition = "bytea") public byte[] imageBytes;
  @Column(name = "created_at", nullable = false) public Instant createdAt = Instant.now();

  protected AiAssessment() {}

  AiAssessment(UUID patientId, UUID patientIdentityId) {
    this.id = UUID.randomUUID();
    this.patientId = patientId;
    this.patientIdentityId = patientIdentityId;
  }
}
