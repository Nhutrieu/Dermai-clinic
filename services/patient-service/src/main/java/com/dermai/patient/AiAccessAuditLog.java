package com.dermai.patient;

import jakarta.persistence.*;
import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name = "ai_access_audit_logs")
class AiAccessAuditLog {
  @Id UUID id;
  @Column(name = "assessment_id") UUID assessmentId;
  @Column(name = "patient_identity_id") UUID patientIdentityId;
  @Column(name = "actor_identity_id", nullable = false) UUID actorIdentityId;
  @Column(name = "actor_role", nullable = false, length = 20) String actorRole;
  @Column(name = "action_type", nullable = false, length = 50) String actionType;
  @Column(name = "source_ip", length = 64) String sourceIp;
  @Column(name = "user_agent", length = 500) String userAgent;
  @Column(name = "created_at", nullable = false) Instant createdAt;

  protected AiAccessAuditLog() {}

  AiAccessAuditLog(UUID assessmentId, UUID patientIdentityId, UUID actorIdentityId,
      String actorRole, String actionType, String sourceIp, String userAgent) {
    this.id = UUID.randomUUID();
    this.assessmentId = assessmentId;
    this.patientIdentityId = patientIdentityId;
    this.actorIdentityId = actorIdentityId;
    this.actorRole = actorRole;
    this.actionType = actionType;
    this.sourceIp = sourceIp;
    this.userAgent = userAgent;
    this.createdAt = Instant.now();
  }
}
