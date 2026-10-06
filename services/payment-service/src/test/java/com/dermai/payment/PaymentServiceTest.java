package com.dermai.payment;
import static org.assertj.core.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.math.BigDecimal;
import java.time.*;
import java.util.*;
import org.junit.jupiter.api.*;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.support.SimpleTransactionStatus;

class PaymentServiceTest{
 private PaymentRepository payments;private PaymentOutboxRepository outbox;private PayOSGateway payOS;private PaymentService service;
 private OrderCodeGenerator orderCodes;private BookingClient bookings;private DepositSettingsService depositSettings;

 @BeforeEach void setUp(){
  payments=mock(PaymentRepository.class);outbox=mock(PaymentOutboxRepository.class);payOS=mock(PayOSGateway.class);
  orderCodes=mock(OrderCodeGenerator.class);bookings=mock(BookingClient.class);
  var manager=mock(PlatformTransactionManager.class);when(manager.getTransaction(any())).thenReturn(new SimpleTransactionStatus());
  depositSettings=mock(DepositSettingsService.class);
  when(depositSettings.current()).thenReturn(new DepositSettingsService.DepositSetting(new BigDecimal("100000"),null,null));
  service=new PaymentService(payments,outbox,orderCodes,payOS,bookings,new ObjectMapper().findAndRegisterModules(),
    Clock.fixed(Instant.parse("2026-09-21T03:00:00Z"),ZoneOffset.UTC),manager,depositSettings,Duration.ofMinutes(10),"https://app/success","https://app/cancel");
 }

 @Test void receptionistPaymentStoresRecipientAndPublishesEmailLinkEvent(){
  when(depositSettings.current()).thenReturn(new DepositSettingsService.DepositSetting(new BigDecimal("125000"),null,null));
  var bookingId=UUID.randomUUID();var patientIdentityId=UUID.randomUUID();
  var stored=new java.util.concurrent.atomic.AtomicReference<Payment>();
  when(payments.findByBookingIdAndPatientIdentityId(bookingId,patientIdentityId)).thenReturn(Optional.empty());
  when(payments.findByBookingId(bookingId)).thenReturn(Optional.empty());
  when(bookings.preparePayment(bookingId,patientIdentityId)).thenReturn(new BookingClient.BookingDetails(bookingId,patientIdentityId,Instant.parse("2026-09-21T05:00:00Z"),"PENDING_PAYMENT",null,null));
  when(orderCodes.next()).thenReturn(123456L);
  when(payments.saveAndFlush(any(Payment.class))).thenAnswer(invocation->{var payment=invocation.getArgument(0,Payment.class);stored.set(payment);return payment;});
  when(payments.findById(any())).thenAnswer(invocation->Optional.ofNullable(stored.get()));
  when(payments.save(any(Payment.class))).thenAnswer(invocation->invocation.getArgument(0));
  when(payOS.create(anyLong(),anyLong(),anyString(),anyString(),anyString(),any())).thenReturn(new PayOSGateway.PaymentLinkResult("link-id","https://checkout.example/123","qr-data"));

  var result=service.create(bookingId,patientIdentityId," Patient@Example.com ");

  assertThat(result.status()).isEqualTo(PaymentStatus.PENDING);
  assertThat(result.amount()).isEqualByComparingTo("125000");
  assertThat(result.recipientEmail()).isEqualTo("patient@example.com");
  var event=org.mockito.ArgumentCaptor.forClass(PaymentOutboxEvent.class);
  verify(outbox).save(event.capture());
  assertThat(event.getValue().routingKey).isEqualTo("payment.link_created");
  assertThat(event.getValue().payload).contains("patient@example.com").contains("https://checkout.example/123");
 }
 @Test void successfulWebhookIsIdempotentAndPublishesOnePaidEvent(){
  var payment=pendingPayment();
  when(payOS.verify(any())).thenReturn(new PayOSGateway.VerifiedWebhook(payment.orderCode,100000L,"bank-reference",payment.paymentLinkId,"00"));
  when(payments.findByOrderCode(payment.orderCode)).thenReturn(Optional.of(payment));

  assertThat(service.handleWebhook(Map.of())).isTrue();
  assertThat(service.handleWebhook(Map.of())).isTrue();

  assertThat(payment.status).isEqualTo(PaymentStatus.SUCCESS);
  assertThat(payment.payosTransId).isEqualTo("bank-reference");
  verify(outbox,times(1)).save(any(PaymentOutboxEvent.class));
 }

 @Test void validSignatureWithWrongAmountDoesNotConfirmTheBooking(){
  var payment=pendingPayment();
  when(payOS.verify(any())).thenReturn(new PayOSGateway.VerifiedWebhook(payment.orderCode,99999L,"bank-reference",payment.paymentLinkId,"00"));
  when(payments.findByOrderCode(payment.orderCode)).thenReturn(Optional.of(payment));

  assertThatThrownBy(()->service.handleWebhook(Map.of())).isInstanceOf(WebhookMismatchException.class).hasMessage("AMOUNT_MISMATCH");
  assertThat(payment.status).isEqualTo(PaymentStatus.PENDING);
  verifyNoInteractions(outbox);
 }

 @Test void patientCancellationCancelsPayOSAndPublishesBookingCancellation(){
  var payment=pendingPayment();
  when(payments.findByOrderCode(payment.orderCode)).thenReturn(Optional.of(payment));
  when(payments.findById(payment.id)).thenReturn(Optional.of(payment));

  var result=service.cancel(payment.orderCode,payment.patientIdentityId);

  assertThat(result.status()).isEqualTo(PaymentStatus.CANCELLED);
  verify(payOS).cancel(payment.orderCode,"Patient cancelled payment");
  var event=org.mockito.ArgumentCaptor.forClass(PaymentOutboxEvent.class);
  verify(outbox).save(event.capture());
  assertThat(event.getValue().routingKey).isEqualTo("booking.payment_cancelled");
  assertThat(event.getValue().payload).contains("status").contains("CANCELLED");
 }

 @Test void anotherPatientCannotCancelThePayment(){
  var payment=pendingPayment();
  when(payments.findByOrderCode(payment.orderCode)).thenReturn(Optional.of(payment));

  assertThatThrownBy(()->service.cancel(payment.orderCode,UUID.randomUUID())).isInstanceOf(PaymentForbidden.class);
  assertThat(payment.status).isEqualTo(PaymentStatus.PENDING);
  verifyNoInteractions(payOS,outbox);
 }
 @Test void clinicCancellationRequestsAFullRefundAndIsIdempotent(){
  var payment=pendingPayment();payment.status=PaymentStatus.SUCCESS;
  var actor=UUID.randomUUID();
  when(payments.findLockedByBookingId(payment.bookingId)).thenReturn(Optional.of(payment));

  var first=service.requestRefund(payment.bookingId,actor,"RECEPTIONIST","CLINIC","Bác sĩ nghỉ đột xuất");
  var second=service.requestRefund(payment.bookingId,actor,"RECEPTIONIST","CLINIC","Bác sĩ nghỉ đột xuất");

  assertThat(first).isPresent();assertThat(second).isPresent();
  assertThat(payment.status).isEqualTo(PaymentStatus.REFUND_REQUESTED);
  assertThat(payment.refundAmount).isEqualByComparingTo("100000");
  assertThat(payment.refundInitiator).isEqualTo("CLINIC");
  assertThat(payment.refundRequestedByIdentity).isEqualTo(actor);
  var event=org.mockito.ArgumentCaptor.forClass(PaymentOutboxEvent.class);
  verify(outbox,times(1)).save(event.capture());
  assertThat(event.getValue().routingKey).isEqualTo("payment.refund_requested");
 }

 @Test void patientMustExplicitlyRequestRefundAfterCancellingPaidAppointment(){
  var payment=pendingPayment();payment.status=PaymentStatus.SUCCESS;
  when(bookings.get(payment.bookingId)).thenReturn(new BookingClient.BookingDetails(payment.bookingId,payment.patientIdentityId,payment.appointmentStartAt,"CANCELLED","Không còn nhu cầu","PATIENT_REQUEST"));
  when(payments.findLockedByBookingId(payment.bookingId)).thenReturn(Optional.of(payment));

  var result=service.requestPatientRefund(payment.bookingId,payment.patientIdentityId,null);

  assertThat(result.status()).isEqualTo(PaymentStatus.REFUND_REQUESTED);
  assertThat(payment.refundInitiator).isEqualTo("PATIENT_REQUEST");
  assertThat(payment.refundReason).isEqualTo("Không còn nhu cầu");
  assertThat(payment.refundAmount).isEqualByComparingTo("100000");
  var event=org.mockito.ArgumentCaptor.forClass(PaymentOutboxEvent.class);verify(outbox).save(event.capture());
  assertThat(event.getValue().routingKey).isEqualTo("payment.refund_requested");
 }

 @Test void receptionistCancellingForPatientQueuesPolicyRefundOnce(){
  var payment=pendingPayment();payment.status=PaymentStatus.SUCCESS;
  payment.createdAt=Instant.parse("2026-09-20T00:00:00Z");payment.appointmentStartAt=Instant.parse("2026-09-21T15:00:00Z");
  var actor=UUID.randomUUID();when(payments.findLockedByBookingId(payment.bookingId)).thenReturn(Optional.of(payment));

  var first=service.requestPatientRefundOnBehalf(payment.bookingId,actor,"RECEPTIONIST","Bệnh nhân gọi hủy");
  var second=service.requestPatientRefundOnBehalf(payment.bookingId,actor,"RECEPTIONIST","Bệnh nhân gọi hủy");

  assertThat(first).isPresent();assertThat(second).isPresent();
  assertThat(payment.status).isEqualTo(PaymentStatus.REFUND_REQUESTED);
  assertThat(payment.refundAmount).isEqualByComparingTo("50000");
  assertThat(payment.refundInitiator).isEqualTo("PATIENT_REQUEST");
  assertThat(payment.refundRequestedByRole).isEqualTo("RECEPTIONIST");
  assertThat(payment.refundRequestedByIdentity).isEqualTo(actor);
  verify(outbox,times(1)).save(any(PaymentOutboxEvent.class));
 }
 @Test void receptionistCancellationDoesNotQueueRefundWithoutPaidEligibleDeposit(){
  var payment=pendingPayment();var actor=UUID.randomUUID();
  when(payments.findLockedByBookingId(payment.bookingId)).thenReturn(Optional.of(payment));

  assertThat(service.requestPatientRefundOnBehalf(payment.bookingId,actor,"RECEPTIONIST","Bệnh nhân gọi hủy")).isEmpty();
  payment.status=PaymentStatus.SUCCESS;payment.createdAt=Instant.parse("2026-09-20T00:00:00Z");
  assertThat(service.requestPatientRefundOnBehalf(payment.bookingId,actor,"RECEPTIONIST","Bệnh nhân gọi hủy")).isEmpty();
  assertThat(payment.status).isEqualTo(PaymentStatus.SUCCESS);
  verifyNoInteractions(outbox);
 }
 @Test void patientCannotRequestRefundForClinicInitiatedCancellation(){
  var payment=pendingPayment();payment.status=PaymentStatus.SUCCESS;
  when(bookings.get(payment.bookingId)).thenReturn(new BookingClient.BookingDetails(payment.bookingId,payment.patientIdentityId,payment.appointmentStartAt,"CANCELLED","Bác sĩ nghỉ","CLINIC"));

  assertThatThrownBy(()->service.requestPatientRefund(payment.bookingId,payment.patientIdentityId,null))
   .isInstanceOf(PaymentConflict.class).hasMessage("PATIENT_REFUND_REQUEST_NOT_ALLOWED");
  verifyNoInteractions(outbox);
 }
 @Test void policyRefundsHalfWhenRequestIsBetweenSixAndTwentyFourHoursBeforeAppointment(){
  var payment=pendingPayment();payment.status=PaymentStatus.SUCCESS;payment.createdAt=Instant.parse("2026-09-20T00:00:00Z");payment.appointmentStartAt=Instant.parse("2026-09-21T15:00:00Z");
  when(bookings.get(payment.bookingId)).thenReturn(new BookingClient.BookingDetails(payment.bookingId,payment.patientIdentityId,payment.appointmentStartAt,"CANCELLED","Không còn nhu cầu","PATIENT_REQUEST"));
  when(payments.findLockedByBookingId(payment.bookingId)).thenReturn(Optional.of(payment));

  var result=service.requestPatientRefund(payment.bookingId,payment.patientIdentityId,null);

  assertThat(result.refundAmount()).isEqualByComparingTo("50000");
  assertThat(result.status()).isEqualTo(PaymentStatus.REFUND_REQUESTED);
 }

 @Test void policyRejectsRefundWhenRequestIsUnderSixHoursBeforeAppointment(){
  var payment=pendingPayment();payment.status=PaymentStatus.SUCCESS;payment.createdAt=Instant.parse("2026-09-20T00:00:00Z");payment.appointmentStartAt=Instant.parse("2026-09-21T08:00:00Z");
  when(bookings.get(payment.bookingId)).thenReturn(new BookingClient.BookingDetails(payment.bookingId,payment.patientIdentityId,payment.appointmentStartAt,"CANCELLED","Không còn nhu cầu","PATIENT_REQUEST"));
  when(payments.findLockedByBookingId(payment.bookingId)).thenReturn(Optional.of(payment));

  assertThatThrownBy(()->service.requestPatientRefund(payment.bookingId,payment.patientIdentityId,null))
   .isInstanceOf(PaymentConflict.class).hasMessage("REFUND_NOT_ELIGIBLE_UNDER_6_HOURS");
  assertThat(payment.status).isEqualTo(PaymentStatus.SUCCESS);
  verifyNoInteractions(outbox);
 }

 @Test void receptionistCannotOverridePolicyRefundAmount(){
  var payment=pendingPayment();payment.status=PaymentStatus.REFUND_REQUESTED;payment.refundInitiator="PATIENT_REQUEST";payment.refundAmount=new BigDecimal("50000");
  when(payments.findById(payment.id)).thenReturn(Optional.of(payment));

  assertThatThrownBy(()->service.completeRefund(payment.id,new BigDecimal("100000"),"BANK_TRANSFER","RF-1",null,null,UUID.randomUUID(),"RECEPTIONIST"))
   .isInstanceOf(PaymentConflict.class).hasMessage("REFUND_AMOUNT_MUST_MATCH_POLICY");
  assertThat(payment.status).isEqualTo(PaymentStatus.REFUND_REQUESTED);
 }
 @Test void staffCompletesPatientRefundWithAmountReferenceAndAudit(){
  var payment=pendingPayment();payment.status=PaymentStatus.REFUND_REQUESTED;payment.refundInitiator="PATIENT_REQUEST";payment.refundAmount=new BigDecimal("50000");
  var actor=UUID.randomUUID();when(payments.findById(payment.id)).thenReturn(Optional.of(payment));

  var result=service.completeRefund(payment.id,new BigDecimal("50000"),"BANK_TRANSFER"," RF-2026-001 ",null,null,actor,"RECEPTIONIST");

  assertThat(result.status()).isEqualTo(PaymentStatus.REFUNDED);
  assertThat(result.refundAmount()).isEqualByComparingTo("50000");
  assertThat(result.refundReference()).isEqualTo("RF-2026-001");
  assertThat(result.refundCompletedByIdentity()).isEqualTo(actor);
  assertThat(result.refundCompletedByRole()).isEqualTo("RECEPTIONIST");
  var event=org.mockito.ArgumentCaptor.forClass(PaymentOutboxEvent.class);verify(outbox).save(event.capture());
  assertThat(event.getValue().routingKey).isEqualTo("payment.refunded");
 }

 @Test void adminCannotCompleteRefund(){
  var payment=pendingPayment();payment.status=PaymentStatus.REFUND_REQUESTED;payment.refundInitiator="PATIENT_REQUEST";payment.refundAmount=new BigDecimal("50000");

  assertThatThrownBy(()->service.completeRefund(payment.id,new BigDecimal("50000"),"BANK_TRANSFER","RF-1",null,null,UUID.randomUUID(),"ADMIN"))
   .isInstanceOf(PaymentForbidden.class);
  verifyNoInteractions(payments,outbox);
 }
 @Test void bankTransferCanUseReceiptImageWithoutTransactionReference(){
  var payment=pendingPayment();payment.status=PaymentStatus.REFUND_REQUESTED;payment.refundInitiator="PATIENT_REQUEST";payment.refundAmount=new BigDecimal("100000");
  var actor=UUID.randomUUID();when(payments.findById(payment.id)).thenReturn(Optional.of(payment));
  var evidence=new PaymentService.RefundEvidence("image/png","bien-lai.png",new byte[]{1,2,3});

  var result=service.completeRefund(payment.id,new BigDecimal("100000"),"BANK_TRANSFER",null,null,evidence,actor,"RECEPTIONIST");

  assertThat(result.status()).isEqualTo(PaymentStatus.REFUNDED);
  assertThat(result.refundReference()).isNull();
  assertThat(result.refundMethod()).isEqualTo("BANK_TRANSFER");
  assertThat(result.refundEvidenceAvailable()).isTrue();
  assertThat(result.refundEvidenceOriginalName()).isEqualTo("bien-lai.png");
 }

 @Test void refundEvidenceUsesUnlockedReadQuery(){
  var payment=pendingPayment();payment.refundEvidenceContentType="image/png";payment.refundEvidenceOriginalName="bien-lai.png";payment.refundEvidenceData=new byte[]{1,2,3};
  when(payments.findUnlockedById(payment.id)).thenReturn(Optional.of(payment));

  var result=service.refundEvidence(payment.id);

  assertThat(result.contentType()).isEqualTo("image/png");
  assertThat(result.originalName()).isEqualTo("bien-lai.png");
  assertThat(result.data()).containsExactly(1,2,3);
  verify(payments).findUnlockedById(payment.id);
  verify(payments,never()).findById(payment.id);
 }
 @Test void cashRefundGeneratesReceiptNumberAndStoresRecipient(){
  var payment=pendingPayment();payment.status=PaymentStatus.REFUND_REQUESTED;payment.refundInitiator="PATIENT_REQUEST";payment.refundAmount=new BigDecimal("50000");
  var actor=UUID.randomUUID();when(payments.findById(payment.id)).thenReturn(Optional.of(payment));

  var result=service.completeRefund(payment.id,new BigDecimal("50000"),"CASH",null," Nguyễn Văn A ",null,actor,"RECEPTIONIST");

  assertThat(result.status()).isEqualTo(PaymentStatus.REFUNDED);
  assertThat(result.refundMethod()).isEqualTo("CASH");
  assertThat(result.refundReference()).isNull();
  assertThat(result.refundRecipientName()).isEqualTo("Nguyễn Văn A");
  assertThat(result.refundReceiptNumber()).isEqualTo("HT-20260921-123456");
 }

 @Test void bankTransferWithoutReferenceOrEvidenceIsRejected(){
  var payment=pendingPayment();payment.status=PaymentStatus.REFUND_REQUESTED;payment.refundInitiator="PATIENT_REQUEST";payment.refundAmount=new BigDecimal("50000");
  when(payments.findById(payment.id)).thenReturn(Optional.of(payment));

  assertThatThrownBy(()->service.completeRefund(payment.id,new BigDecimal("50000"),"BANK_TRANSFER",null,null,null,UUID.randomUUID(),"RECEPTIONIST"))
   .isInstanceOf(PaymentConflict.class).hasMessage("REFUND_TRANSFER_PROOF_REQUIRED");
  assertThat(payment.status).isEqualTo(PaymentStatus.REFUND_REQUESTED);
  verifyNoInteractions(outbox);
 }
 @Test void clinicCancellationCannotBeMarkedWithAPartialRefund(){
  var payment=pendingPayment();payment.status=PaymentStatus.REFUND_REQUESTED;payment.refundInitiator="CLINIC";
  when(payments.findById(payment.id)).thenReturn(Optional.of(payment));

  assertThatThrownBy(()->service.completeRefund(payment.id,new BigDecimal("50000"),"BANK_TRANSFER","RF-1",null,null,UUID.randomUUID(),"RECEPTIONIST"))
   .isInstanceOf(PaymentConflict.class).hasMessage("REFUND_AMOUNT_MUST_MATCH_POLICY");
  assertThat(payment.status).isEqualTo(PaymentStatus.REFUND_REQUESTED);
  verifyNoInteractions(outbox);
 }
 @Test void reconciliationRecoversPaidOrderWhenWebhookWasMissed(){
  var payment=pendingPayment();
  when(payments.findByOrderCode(payment.orderCode)).thenReturn(Optional.of(payment));
  when(payOS.get(payment.orderCode)).thenReturn(new PayOSGateway.PaymentLinkStatusResult(payment.paymentLinkId,100000L,100000L,"PAID","bank-reference"));

  var result=service.reconcile(payment.orderCode,payment.patientIdentityId,"PATIENT");

  assertThat(result.status()).isEqualTo(PaymentStatus.SUCCESS);
  assertThat(payment.payosTransId).isEqualTo("bank-reference");
  verify(outbox).save(any(PaymentOutboxEvent.class));
 }
 @Test void adminReportUsesTheRequestedWindowWithoutARecordLimit(){
  var from=Instant.parse("2026-09-01T00:00:00Z");var to=Instant.parse("2026-10-01T00:00:00Z");
  var payment=pendingPayment();payment.status=PaymentStatus.REFUNDED;
  when(payments.findReportPayments(from,to)).thenReturn(List.of(payment));

  assertThat(service.report(from,to)).extracting(PaymentService.PaymentResponse::status).containsExactly(PaymentStatus.REFUNDED);
  verify(payments).findReportPayments(from,to);
  verify(payments,never()).findAll();
 }
 private Payment pendingPayment(){
  var now=Instant.parse("2026-09-21T03:00:00Z");
  var payment=Payment.creating(UUID.randomUUID(),UUID.randomUUID(),new BigDecimal("100000"),123456L,now.plusSeconds(3600),now.plusSeconds(600),now);
  payment.status=PaymentStatus.PENDING;payment.paymentLinkId="pay-link-id";return payment;
 }
}
