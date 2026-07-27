package com.dermai.appointment;
import jakarta.persistence.*;import java.time.*;import java.util.*;
@Entity @Table(name="appointments")
public class Appointment{
 @Id public UUID id;@Column(name="patient_id",nullable=false) public UUID patientId;@Column(name="patient_identity_id",nullable=false) public UUID patientIdentityId;@Column(name="doctor_id") public UUID doctorId;@Column(name="doctor_identity_id") public UUID doctorIdentityId;
 @Column(name="parent_id") public UUID parentId;@Column(name="start_at",nullable=false) public Instant startAt;@Column(name="end_at",nullable=false) public Instant endAt;
 @Enumerated(EnumType.STRING) @Column(nullable=false) public AppointmentStatus status;
 @Column(length=500) public String reason;@Column(name="cancel_reason",length=500) public String cancelReason;
 @Column(name="follow_up_reason",length=500) public String followUpReason;
 @Column(name="follow_up_not_before") public Instant followUpNotBefore;
 @Column(name="patient_hidden",nullable=false) public boolean patientHidden=false;
 @Column(name="hold_expires_at") public Instant holdExpiresAt;
 @Column(name="idempotency_key",unique=true) public String idempotencyKey;@Version public long version;
 @Column(name="created_at") public Instant createdAt=Instant.now();@Column(name="updated_at") public Instant updatedAt=Instant.now();
 protected Appointment(){}
 public static Appointment pending(UUID patient,UUID patientIdentity,UUID doctor,UUID doctorIdentity,Instant start,Instant end,String reason,String key){
  var x=new Appointment();x.id=UUID.randomUUID();x.patientId=patient;x.patientIdentityId=patientIdentity;x.doctorId=doctor;x.doctorIdentityId=doctorIdentity;x.startAt=start;x.endAt=end;x.reason=reason;x.idempotencyKey=key;x.status=doctor==null?AppointmentStatus.PENDING:AppointmentStatus.ASSIGNED;return x;
 }
 public static Appointment held(UUID patient,UUID patientIdentity,UUID doctor,UUID doctorIdentity,Instant start,Instant end){
  var x=pending(patient,patientIdentity,doctor,doctorIdentity,start,end,null,null);x.status=AppointmentStatus.HELD;x.holdExpiresAt=Instant.now().plus(Duration.ofMinutes(5));return x;
 }
 public static Appointment proposed(UUID patient,UUID patientIdentity,UUID doctor,UUID doctorIdentity,Instant start,Instant end,String reason){
  var x=pending(patient,patientIdentity,doctor,doctorIdentity,start,end,reason,null);x.status=AppointmentStatus.PROPOSED;x.holdExpiresAt=Instant.now().plus(Duration.ofMinutes(10));return x;
 }
 public void transition(AppointmentStatus next){if(!status.mayTransitionTo(next))throw new IllegalStateException("INVALID_TRANSITION");status=next;updatedAt=Instant.now();}
}
