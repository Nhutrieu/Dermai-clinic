package com.dermai.appointment;
import jakarta.persistence.*;import java.time.*;import java.util.*;
@Entity @Table(name="appointment_notifications") public class AppointmentNotification{
 @Id public UUID id;@Column(name="patient_identity_id",nullable=false) public UUID patientIdentityId;@Column(name="appointment_id") public UUID appointmentId;@Column(name="notification_type",nullable=false,length=100) public String notificationType;@Column(nullable=false,length=160) public String title;@Column(nullable=false,length=500) public String body;@Column(name="created_at") public Instant createdAt=Instant.now();@Column(name="read_at") public Instant readAt;
 protected AppointmentNotification(){} AppointmentNotification(Appointment a,String type,String title,String body){id=UUID.randomUUID();patientIdentityId=a.patientIdentityId;appointmentId=a.id;notificationType=type;this.title=title;this.body=body;}
}
