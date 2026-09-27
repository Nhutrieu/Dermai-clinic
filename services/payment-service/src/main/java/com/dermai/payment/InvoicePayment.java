package com.dermai.payment;

import jakarta.persistence.*;
import java.math.BigDecimal;
import java.time.Instant;
import java.util.UUID;

@Entity @Table(name="invoice_payments")
public class InvoicePayment {
 @Id public UUID id;
 @Column(name="invoice_id",nullable=false,unique=true) public UUID invoiceId;
 @Column(name="patient_identity_id",nullable=false) public UUID patientIdentityId;
 @Column(nullable=false,precision=12,scale=0) public BigDecimal amount;
 @Column(name="order_code",nullable=false,unique=true) public Long orderCode;
 @Enumerated(EnumType.STRING) @Column(nullable=false) public PaymentStatus status;
 @Column(name="payos_trans_id",unique=true) public String payosTransId;
 @Column(name="payment_link_id",unique=true) public String paymentLinkId;
 @Column(name="checkout_url") public String checkoutUrl;
 @Column(name="qr_code") public String qrCode;
 @Column(name="expires_at",nullable=false) public Instant expiresAt;
 @Column(name="created_at",nullable=false) public Instant createdAt;
 @Column(name="updated_at",nullable=false) public Instant updatedAt;
 @Version public long version;
 protected InvoicePayment(){}
}