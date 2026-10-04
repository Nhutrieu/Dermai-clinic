package com.dermai.appointment;

import jakarta.persistence.*;
import java.math.BigDecimal;
import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name="appointment_performed_services", uniqueConstraints=@UniqueConstraint(name="uq_appointment_performed_service", columnNames={"appointment_id","service_id"}))
public class AppointmentPerformedService {
 @Id public UUID id;
 @Column(name="appointment_id",nullable=false) public UUID appointmentId;
 @Column(name="service_id",nullable=false) public UUID serviceId;
 @Column(name="service_code",nullable=false,length=80) public String serviceCode;
 @Column(name="service_name",nullable=false,length=160) public String serviceName;
 @Column(name="unit_price",nullable=false,precision=12,scale=0) public BigDecimal unitPrice;
 @Column(name="confirmed_by",nullable=false) public UUID confirmedBy;
 @Column(name="confirmed_at",nullable=false) public Instant confirmedAt;
}
