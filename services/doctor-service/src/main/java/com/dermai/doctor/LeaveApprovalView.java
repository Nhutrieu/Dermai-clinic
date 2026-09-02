package com.dermai.doctor;

import jakarta.persistence.*;
import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name = "leave_approval_views", uniqueConstraints = @UniqueConstraint(
    name = "uq_leave_approval_view", columnNames = {"leave_id", "receptionist_identity_id"}))
class LeaveApprovalView {
  @Id UUID id;
  @Column(name = "leave_id", nullable = false) UUID leaveId;
  @Column(name = "receptionist_identity_id", nullable = false) UUID receptionistIdentityId;
  @Column(name = "viewed_at", nullable = false) Instant viewedAt = Instant.now();

  protected LeaveApprovalView() {}

  LeaveApprovalView(UUID leaveId, UUID receptionistIdentityId) {
    this.id = UUID.randomUUID();
    this.leaveId = leaveId;
    this.receptionistIdentityId = receptionistIdentityId;
  }
}