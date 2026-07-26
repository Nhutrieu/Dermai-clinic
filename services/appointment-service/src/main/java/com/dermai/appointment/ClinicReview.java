package com.dermai.appointment;
import jakarta.persistence.*;import java.time.*;import java.util.*;
@Entity @Table(name="clinic_reviews")
public class ClinicReview{
 @Id public UUID id;@Column(name="appointment_id",nullable=false,unique=true)public UUID appointmentId;@Column(name="patient_identity_id",nullable=false)public UUID patientIdentityId;
 @Column(name="display_name",nullable=false,length=120)public String displayName;public short rating;@Column(nullable=false,length=1000)public String comment;@Enumerated(EnumType.STRING)public Status status=Status.PENDING;
 @Column(name="created_at")public Instant createdAt=Instant.now();@Column(name="updated_at")public Instant updatedAt=Instant.now();protected ClinicReview(){}
 public ClinicReview(Appointment a,String name,short rating,String comment){id=UUID.randomUUID();appointmentId=a.id;patientIdentityId=a.patientIdentityId;displayName=abbreviate(name);this.rating=rating;this.comment=comment.trim();}
 static String abbreviate(String name){var parts=name.trim().split("\\s+");return parts.length==1?parts[0].charAt(0)+".":parts[parts.length-1]+" "+parts[0].charAt(0)+".";}
 enum Status{PENDING,APPROVED,HIDDEN}
}
