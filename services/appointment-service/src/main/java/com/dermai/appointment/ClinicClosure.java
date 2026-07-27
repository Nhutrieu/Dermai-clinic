package com.dermai.appointment;
import jakarta.persistence.*;import java.time.*;import java.util.*;
@Entity @Table(name="clinic_closures") public class ClinicClosure{
 @Id public UUID id;@Column(name="closure_date",nullable=false,unique=true) public LocalDate closureDate;@Column(nullable=false,length=300) public String reason;@Column(name="created_at") public Instant createdAt=Instant.now();
 protected ClinicClosure(){} ClinicClosure(LocalDate date,String reason){id=UUID.randomUUID();closureDate=date;this.reason=reason.trim();}
}
