package com.dermai.appointment;

import jakarta.persistence.*;
import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name="support_conversations")
public class SupportConversation {
 @Id @Column(name="patient_identity_id") public UUID patientIdentityId;
 @Column(name="assigned_receptionist_identity_id") public UUID assignedReceptionistIdentityId;
 @Column(name="assigned_at") public Instant assignedAt;
 @Column(name="channel_status",nullable=false) public String channelStatus;
 @Column(name="ai_failure_count",nullable=false) public int aiFailureCount;
 @Column(name="last_intent") public String lastIntent;
 @Column(name="last_intent_confidence") public Double lastIntentConfidence;
 @Column(name="ai_summary",length=4000) public String aiSummary;
 @Column(name="escalation_reason") public String escalationReason;
 @Column(name="escalated_at") public Instant escalatedAt;
 @Column(name="resolved_at") public Instant resolvedAt;
 @Column(name="resolved_by_identity_id") public UUID resolvedByIdentityId;
 @Column(name="updated_at",nullable=false) public Instant updatedAt;

 protected SupportConversation(){}
 SupportConversation(UUID patientIdentityId){this.patientIdentityId=patientIdentityId;channelStatus="AI_ACTIVE";updatedAt=Instant.now();}
}
