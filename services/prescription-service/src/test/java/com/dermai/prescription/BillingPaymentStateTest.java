package com.dermai.prescription;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import java.math.BigDecimal;
import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.Optional;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class BillingPaymentStateTest {
 @Test
 void onlinePaymentClearsTheOutstandingBalance(){
  var invoices=mock(InvoiceRepository.class);
  var invoice=new Invoice();
  invoice.id=UUID.randomUUID();
  invoice.status=Invoice.Status.AWAITING_PAYMENT;
  invoice.remainingAmount=new BigDecimal("313000");
  when(invoices.findById(invoice.id)).thenReturn(Optional.of(invoice));
  when(invoices.save(invoice)).thenReturn(invoice);
  var paidAt=Instant.parse("2026-09-26T06:00:00Z");
  var receptionEvents=mock(BillingReceptionEvents.class);
  var service=new BillingService(
    invoices,
    mock(InvoiceCashPaymentRepository.class),
    mock(InventoryMovementRepository.class),
    mock(InvoiceAdjustmentRepository.class),
    mock(MedicineRepository.class),
    mock(PrescriptionRepository.class),
    "http://appointment-service",
    "http://payment-service",
    "test-token",
    Clock.fixed(paidAt,ZoneOffset.UTC),
    receptionEvents
  );

  service.markOnlinePaid(invoice.id,new BigDecimal("313000"));

  assertThat(invoice.status).isEqualTo(Invoice.Status.PAID);
  assertThat(invoice.remainingAmount).isEqualByComparingTo(BigDecimal.ZERO);
  assertThat(invoice.paidAt).isEqualTo(paidAt);
  verify(invoices).save(invoice);
  verify(receptionEvents).paid(invoice);
 }
}
