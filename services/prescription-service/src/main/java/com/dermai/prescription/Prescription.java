package com.dermai.prescription;
import jakarta.persistence.*;import java.time.*;import java.util.*;
@Entity @Table(name="prescriptions") public class Prescription{
 @Id public UUID id;@Column(name="record_id",nullable=false) public UUID recordId;@Column(name="patient_id",nullable=false) public UUID patientId;@Column(name="patient_identity_id",nullable=false) public UUID patientIdentityId;@Column(name="doctor_id",nullable=false) public UUID doctorId;
 @Column(length=3000) public String instructions;@Column(name="signed_at",nullable=false) public Instant signedAt;
 @ElementCollection(fetch=FetchType.EAGER) @CollectionTable(name="prescription_items",joinColumns=@JoinColumn(name="prescription_id")) public List<Item> items=new ArrayList<>();protected Prescription(){}
 @Embeddable public static class Item{@Column(name="drug_name") public String drugName;public String dosage;public String frequency;public String duration;@Column(name="item_instructions") public String instructions;public Item(){}}
}
