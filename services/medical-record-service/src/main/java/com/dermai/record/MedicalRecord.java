package com.dermai.record;
import jakarta.persistence.*;import java.time.*;import java.util.*;
@Entity @Table(name="medical_records") public class MedicalRecord{
 @Id public UUID id;@Column(name="appointment_id",unique=true,nullable=false) public UUID appointmentId;@Column(name="patient_id",nullable=false) public UUID patientId;@Column(name="patient_identity_id",nullable=false) public UUID patientIdentityId;
 @Column(name="doctor_id",nullable=false) public UUID doctorId;@Column(name="final_diagnosis",nullable=false,length=2000) public String finalDiagnosis;
 @Column(name="clinical_notes",length=10000) public String clinicalNotes;@Column(name="treatment_plan",length=5000) public String treatmentPlan;
 @Enumerated(EnumType.STRING) public Severity severity;@Column(name="follow_up_at") public Instant followUpAt;@Column(name="signed_at") public Instant signedAt;
 @Version public long version;protected MedicalRecord(){}
 enum Severity{MILD,MODERATE,SEVERE,URGENT}
}
