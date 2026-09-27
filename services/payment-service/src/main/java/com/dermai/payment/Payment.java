package com.dermai.payment;

import jakarta.persistence.*;
import java.math.BigDecimal;
import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name = "payments")
public class Payment {
  @Id public UUID id;
  @Column(name = "booking_id", nullable = false, unique = true) public UUID bookingId;
  @Column(name = "patient_identity_id", nullable = false) public UUID patientIdentityId;
  @Column(nullable = false, precision = 12, scale = 0) public BigDecimal amount;
  @Column(name = "order_code", nullable = false, unique = true) public Long orderCode;
  @Enumerated(EnumType.STRING) @Column(nullable = false) public PaymentStatus status;
  @Column(name = "payos_trans_id", unique = true) public String payosTransId;
  @Column(name = "payment_link_id", unique = true) public String paymentLinkId;
  @Column(name = "checkout_url") public String checkoutUrl;
  @Column(name = "qr_code") public String qrCode;
  @Column(name = "appointment_start_at", nullable = false) public Instant appointmentStartAt;
  @Column(name = "expires_at", nullable = false) public Instant expiresAt;
  @Column(name = "created_at", nullable = false) public Instant createdAt;
  @Column(name = "recipient_email", length = 320) public String recipientEmail;
  @Column(name = "refund_reason", length = 500) public String refundReason;
  @Column(name = "refund_requested_by_role", length = 30) public String refundRequestedByRole;
  @Column(name = "refund_requested_at") public Instant refundRequestedAt;
  @Column(name = "refunded_at") public Instant refundedAt;
  @Column(name = "refund_reference", length = 200) public String refundReference;
  @Column(name = "refund_requested_by_identity") public UUID refundRequestedByIdentity;
  @Column(name = "refund_initiator", length = 30) public String refundInitiator;
  @Column(name = "refund_amount", precision = 12, scale = 0) public BigDecimal refundAmount;
  @Column(name = "refund_completed_by_identity") public UUID refundCompletedByIdentity;
  @Column(name = "refund_completed_by_role", length = 30) public String refundCompletedByRole;
  @Column(name = "refund_method", length = 30) public String refundMethod;
  @Column(name = "refund_receipt_number", length = 100) public String refundReceiptNumber;
  @Column(name = "refund_recipient_name", length = 200) public String refundRecipientName;
  @Column(name = "refund_evidence_content_type", length = 50) public String refundEvidenceContentType;
  @Column(name = "refund_evidence_original_name", length = 255) public String refundEvidenceOriginalName;
  @Column(name = "refund_evidence_size_bytes") public Long refundEvidenceSizeBytes;
  @Basic(fetch = FetchType.LAZY) @Column(name = "refund_evidence_data") public byte[] refundEvidenceData;
  @Column(name = "updated_at", nullable = false) public Instant updatedAt;
  @Version public long version;

  protected Payment() {}

  static Payment creating(UUID bookingId, UUID patientIdentityId, BigDecimal amount, long orderCode,
      Instant appointmentStartAt, Instant expiresAt, Instant now) {
    return creating(bookingId, patientIdentityId, amount, orderCode, appointmentStartAt, expiresAt, now, null);
  }

  static Payment creating(UUID bookingId, UUID patientIdentityId, BigDecimal amount, long orderCode,
      Instant appointmentStartAt, Instant expiresAt, Instant now, String recipientEmail) {
    var payment = new Payment();
    payment.id = UUID.randomUUID();
    payment.bookingId = bookingId;
    payment.patientIdentityId = patientIdentityId;
    payment.amount = amount;
    payment.orderCode = orderCode;
    payment.appointmentStartAt = appointmentStartAt;
    payment.expiresAt = expiresAt;
    payment.status = PaymentStatus.CREATING;
    payment.recipientEmail = recipientEmail;
    payment.createdAt = now;
    payment.updatedAt = now;
    return payment;
  }
}
