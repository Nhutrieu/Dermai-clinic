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
 @Column(name="updated_at",nullable=false) public Instant updatedAt;

 protected SupportConversation(){}
 SupportConversation(UUID patientIdentityId){this.patientIdentityId=patientIdentityId;updatedAt=Instant.now();}
}
