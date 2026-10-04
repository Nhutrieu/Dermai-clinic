package com.dermai.payment;

import static org.assertj.core.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.math.BigDecimal;
import java.time.*;
import java.util.*;
import org.junit.jupiter.api.*;

class InvoicePaymentServiceTest {
 private InvoicePaymentRepository payments;private PaymentOutboxRepository outbox;private PayOSGateway payOS;private InvoicePaymentService service;

 @BeforeEach void setUp(){payments=mock(InvoicePaymentRepository.class);outbox=mock(PaymentOutboxRepository.class);payOS=mock(PayOSGateway.class);service=new InvoicePaymentService(payments,outbox,mock(OrderCodeGenerator.class),payOS,new ObjectMapper().findAndRegisterModules(),Clock.fixed(Instant.parse("2026-09-28T03:00:00Z"),ZoneOffset.UTC),"https://app/payment/success","https://app/payment/cancel");when(payments.save(any(InvoicePayment.class))).thenAnswer(call->call.getArgument(0));}

 @Test void reconciliationRecoversPaidInvoiceWhenWebhookWasMissed(){var payment=pending();when(payments.findByOrderCode(payment.orderCode)).thenReturn(Optional.of(payment));when(payOS.get(payment.orderCode)).thenReturn(new PayOSGateway.PaymentLinkStatusResult(payment.paymentLinkId,200000L,200000L,"PAID","bank-reference"));
  var result=service.reconcile(payment.orderCode);
  assertThat(result.status()).isEqualTo(PaymentStatus.SUCCESS);assertThat(payment.payosTransId).isEqualTo("bank-reference");var event=org.mockito.ArgumentCaptor.forClass(PaymentOutboxEvent.class);verify(outbox).save(event.capture());assertThat(event.getValue().routingKey).isEqualTo("invoice.paid");assertThat(event.getValue().payload).contains(payment.invoiceId.toString());}

 @Test void anotherPatientCannotReconcileInvoice(){var payment=pending();when(payments.findByOrderCode(payment.orderCode)).thenReturn(Optional.of(payment));assertThatThrownBy(()->service.reconcile(payment.orderCode,UUID.randomUUID(),"PATIENT")).isInstanceOf(PaymentForbidden.class);verifyNoInteractions(payOS,outbox);}

 @Test void cancelledInvoicePaymentCanBeCreatedAgain(){var old=pending();old.status=PaymentStatus.CANCELLED;var codes=mock(OrderCodeGenerator.class);when(codes.next()).thenReturn(987654L);service=new InvoicePaymentService(payments,outbox,codes,payOS,new ObjectMapper().findAndRegisterModules(),Clock.fixed(Instant.parse("2026-09-28T03:00:00Z"),ZoneOffset.UTC),"https://app/payment/success","https://app/payment/cancel");when(payments.findByInvoiceId(old.invoiceId)).thenReturn(Optional.of(old));when(payments.save(any(InvoicePayment.class))).thenAnswer(call->call.getArgument(0));when(payOS.create(anyLong(),anyLong(),anyString(),anyString(),anyString(),any())).thenReturn(new PayOSGateway.PaymentLinkResult("new-link","https://checkout/new","qr"));
  var result=service.create(old.invoiceId,old.patientIdentityId,old.amount);
  assertThat(result.status()).isEqualTo(PaymentStatus.PENDING);assertThat(result.orderCode()).isEqualTo(987654L);}

 private InvoicePayment pending(){var payment=new InvoicePayment();payment.id=UUID.randomUUID();payment.invoiceId=UUID.randomUUID();payment.patientIdentityId=UUID.randomUUID();payment.amount=new BigDecimal("200000");payment.orderCode=123456L;payment.status=PaymentStatus.PENDING;payment.paymentLinkId="invoice-link";payment.expiresAt=Instant.parse("2026-09-28T04:00:00Z");payment.createdAt=Instant.parse("2026-09-28T02:00:00Z");payment.updatedAt=payment.createdAt;return payment;}
}
