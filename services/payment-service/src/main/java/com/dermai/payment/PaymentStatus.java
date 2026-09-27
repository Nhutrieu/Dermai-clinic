package com.dermai.payment;

public enum PaymentStatus {
  CREATING,
  PENDING,
  CANCEL_REQUESTED,
  SUCCESS,
  REFUND_REQUESTED,
  REFUNDED,
  CANCELLED,
  EXPIRED,
  FAILED
}
