package com.dermai.prescription;

import jakarta.persistence.*;
import java.math.BigDecimal;
import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name="invoice_cash_payments")
public class InvoiceCashPayment {
 @Id public UUID id;
 @Column(name="invoice_id",nullable=false,unique=true) public UUID invoiceId;
 @Column(name="amount_due",nullable=false,precision=12,scale=0) public BigDecimal amountDue;
 @Column(name="amount_received",nullable=false,precision=12,scale=0) public BigDecimal amountReceived;
 @Column(name="change_amount",nullable=false,precision=12,scale=0) public BigDecimal changeAmount;
 @Column(name="collected_by",nullable=false) public UUID collectedBy;
 @Column(name="collected_at",nullable=false) public Instant collectedAt;
 @Column(name="cashier_station",nullable=false,length=120) public String cashierStation;
 protected InvoiceCashPayment(){}
}