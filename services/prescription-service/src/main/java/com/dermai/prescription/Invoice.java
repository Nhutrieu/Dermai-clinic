package com.dermai.prescription;

import jakarta.persistence.*;
import java.math.BigDecimal;
import java.time.Instant;
import java.util.*;

@Entity
@Table(name="invoices")
public class Invoice {
 @Id public UUID id;
 @Column(name="appointment_id",nullable=false,unique=true) public UUID appointmentId;
 @Column(name="patient_id",nullable=false) public UUID patientId;
 @Column(name="patient_identity_id",nullable=false) public UUID patientIdentityId;
 @Column(name="prescription_id") public UUID prescriptionId;
 @Column(name="consultation_fee",nullable=false,precision=12,scale=0) public BigDecimal consultationFee;
 @Column(name="service_fee",nullable=false,precision=12,scale=0) public BigDecimal serviceFee;
 @Column(name="medicine_total",nullable=false,precision=12,scale=0) public BigDecimal medicineTotal;
 @Column(name="deposit_applied",nullable=false,precision=12,scale=0) public BigDecimal depositApplied;
 @Column(name="total_amount",nullable=false,precision=12,scale=0) public BigDecimal totalAmount;
 @Column(name="remaining_amount",nullable=false,precision=12,scale=0) public BigDecimal remainingAmount;
 @Enumerated(EnumType.STRING) @Column(name="medicine_fulfillment",nullable=false,length=30) public MedicineFulfillment medicineFulfillment;
 @Enumerated(EnumType.STRING) @Column(nullable=false,length=30) public Status status;
 @Column(name="created_by",nullable=false) public UUID createdBy;
 @Column(name="created_at",nullable=false) public Instant createdAt;
 @Column(name="paid_at") public Instant paidAt;
 @Column(name="dispensed_at") public Instant dispensedAt;
 @Column(name="dispensed_by") public UUID dispensedBy;
 @Version public long version;
 @ElementCollection(fetch=FetchType.EAGER)
 @CollectionTable(name="invoice_items",joinColumns=@JoinColumn(name="invoice_id"))
 public List<Item> items=new ArrayList<>();
 @ElementCollection(fetch=FetchType.EAGER)
 @CollectionTable(name="invoice_service_items",joinColumns=@JoinColumn(name="invoice_id"))
 public List<ServiceItem> serviceItems=new ArrayList<>();
 protected Invoice(){}
 public enum Status {AWAITING_PAYMENT,PAID,DISPENSED,CANCELLED}
 public enum MedicineFulfillment {CLINIC_PHARMACY,OUTSIDE_PHARMACY,NO_PRESCRIPTION}
 @Embeddable public static class ServiceItem {
  @Column(name="service_id",nullable=false) public UUID serviceId;
  @Column(name="service_code",nullable=false,length=80) public String serviceCode;
  @Column(name="service_name",nullable=false,length=160) public String serviceName;
  @Column(name="unit_price",nullable=false,precision=12,scale=0) public BigDecimal unitPrice;
  public ServiceItem(){}
 }
 @Embeddable public static class Item {
  @Column(name="medicine_id",nullable=false) public UUID medicineId;
  @Column(name="medicine_name",nullable=false,length=200) public String medicineName;
  @Column(nullable=false,length=40) public String unit;
  @Column(name="unit_price",nullable=false,precision=12,scale=0) public BigDecimal unitPrice;
  @Column(name="prescribed_quantity",nullable=false) public int prescribedQuantity;
  @Column(name="dispensed_quantity",nullable=false) public int dispensedQuantity;
  @Column(name="line_total",nullable=false,precision=12,scale=0) public BigDecimal lineTotal;
  public Item(){}
 }
}