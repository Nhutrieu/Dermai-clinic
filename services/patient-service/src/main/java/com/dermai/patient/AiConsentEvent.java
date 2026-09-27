package com.dermai.patient;

import jakarta.persistence.*;
import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name = "ai_consent_events")
class AiConsentEvent {
  @Id UUID id;
  @Column(name = "patient_identity_id", nullable = false) UUID patientIdentityId;
  @Column(nullable = false, length = 80) String purpose;
  @Column(name = "policy_version", nullable = false, length = 40) String policyVersion;
  @Column(name = "granted_at", nullable = false) Instant grantedAt;

  protected AiConsentEvent() {}

  AiConsentEvent(UUID patientIdentityId, String purpose, String policyVersion) {
    this.id = UUID.randomUUID();
    this.patientIdentityId = patientIdentityId;
    this.purpose = purpose;
    this.policyVersion = policyVersion;
    this.grantedAt = Instant.now();
  }
}
