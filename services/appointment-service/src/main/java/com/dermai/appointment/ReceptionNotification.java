package com.dermai.appointment;

import jakarta.persistence.*;
import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name = "reception_notifications")
public class ReceptionNotification {
 @Id public UUID id;
 @Column(name = "appointment_id", nullable = false) public UUID appointmentId;
 @Column(name = "patient_identity_id", nullable = false) public UUID patientIdentityId;
 @Column(name = "notification_type", nullable = false, length = 100) public String notificationType;
 @Column(nullable = false, length = 160) public String title;
 @Column(nullable = false, length = 500) public String body;
 @Column(name = "created_at", nullable = false) public Instant createdAt = Instant.now();
 @Column(name = "read_at") public Instant readAt;

 protected ReceptionNotification() {}

 ReceptionNotification(UUID appointmentId, UUID patientIdentityId, String type, String title, String body) {
  id = UUID.randomUUID();
  this.appointmentId = appointmentId;
  this.patientIdentityId = patientIdentityId;
  notificationType = type;
  this.title = title;
  this.body = body;
 }
}