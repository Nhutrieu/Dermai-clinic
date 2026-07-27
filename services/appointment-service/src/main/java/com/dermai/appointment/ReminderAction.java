package com.dermai.appointment;
import jakarta.persistence.*;import java.time.*;import java.util.*;
@Entity @Table(name="reminder_actions") public class ReminderAction{
 @Id public UUID id;@Column(name="appointment_id",nullable=false) public UUID appointmentId;@Column(name="receptionist_identity_id",nullable=false) public UUID receptionistIdentityId;@Column(name="action_type",nullable=false,length=30) public String actionType;@Column(name="created_at") public Instant createdAt=Instant.now();
 protected ReminderAction(){} ReminderAction(UUID appointment,UUID receptionist,String action){id=UUID.randomUUID();appointmentId=appointment;receptionistIdentityId=receptionist;actionType=action;}
}
