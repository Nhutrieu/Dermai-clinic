package com.dermai.appointment;

import jakarta.persistence.*;
import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name="appointment_action_logs")
public class AppointmentActionLog {
 @Id public UUID id;
 @Column(name="appointment_id",nullable=false) public UUID appointmentId;
 @Column(name="actor_identity_id",nullable=false) public UUID actorIdentityId;
 @Column(name="actor_role",nullable=false,length=20) public String actorRole;
 @Column(name="action_type",nullable=false,length=50) public String actionType;
 @Column(name="created_at",nullable=false) public Instant createdAt;

 protected AppointmentActionLog(){}
 AppointmentActionLog(UUID appointmentId,UUID actorIdentityId,String actorRole,String actionType){
  id=UUID.randomUUID();this.appointmentId=appointmentId;this.actorIdentityId=actorIdentityId;this.actorRole=actorRole;this.actionType=actionType;createdAt=Instant.now();
 }
}
