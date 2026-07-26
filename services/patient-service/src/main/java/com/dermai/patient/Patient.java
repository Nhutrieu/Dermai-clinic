package com.dermai.patient;
import jakarta.persistence.*;
import java.time.*;import java.util.*;
@Entity @Table(name="patients")
public class Patient {
 @Id public UUID id;@Column(name="identity_id",nullable=false,unique=true) public UUID identityId;
 @Column(name="full_name",nullable=false) public String fullName;public LocalDate dob;public String phone;
 @Column(name="medical_history") public String medicalHistory;public String allergies;
 @Version public long version;@Column(name="created_at") public Instant createdAt=Instant.now();
 protected Patient(){} public Patient(UUID identity,String name){id=UUID.randomUUID();identityId=identity;fullName=name;}
}
