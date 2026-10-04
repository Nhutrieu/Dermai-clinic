package com.dermai.prescription;

import jakarta.persistence.*;
import java.math.BigDecimal;
import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name="invoice_adjustments")
public class InvoiceAdjustment {
 @Id public UUID id;
 @Column(name="invoice_id",nullable=false) public UUID invoiceId;
 @Column(name="amount_delta",nullable=false,precision=12,scale=0) public BigDecimal amountDelta;
 @Column(nullable=false,length=500) public String reason;
 @Column(name="created_by",nullable=false) public UUID createdBy;
 @Column(name="created_at",nullable=false) public Instant createdAt;
 protected InvoiceAdjustment(){}
}