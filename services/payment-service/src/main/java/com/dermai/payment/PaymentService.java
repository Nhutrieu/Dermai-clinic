package com.dermai.payment;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.math.BigDecimal;
import java.time.*;
import java.util.*;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;

@Service public class PaymentService{
 private final PaymentRepository payments;private final PaymentOutboxRepository outbox;
 private final OrderCodeGenerator orderCodes;private final PayOSGateway payOS;private final BookingClient bookings;
 private final ObjectMapper json;private final Clock clock;private final TransactionTemplate tx;
 private final BigDecimal deposit;private final Duration holdDuration;private final String returnUrl;private final String cancelUrl;

 PaymentService(PaymentRepository payments,PaymentOutboxRepository outbox,OrderCodeGenerator orderCodes,
   PayOSGateway payOS,BookingClient bookings,ObjectMapper json,Clock clock,PlatformTransactionManager transactionManager,
   @Value("${payment.deposit-amount:100000}")BigDecimal deposit,
   @Value("${payment.hold-duration:PT10M}")Duration holdDuration,
   @Value("${payment.return-url}")String returnUrl,@Value("${payment.cancel-url}")String cancelUrl){
  this.payments=payments;this.outbox=outbox;this.orderCodes=orderCodes;this.payOS=payOS;this.bookings=bookings;
  this.json=json;this.clock=clock;this.tx=new TransactionTemplate(transactionManager);this.deposit=deposit;
  this.holdDuration=holdDuration;this.returnUrl=returnUrl;this.cancelUrl=cancelUrl;
 }

 public PaymentResponse create(UUID bookingId,UUID patientIdentityId){
  return create(bookingId,patientIdentityId,null);
 }

 public PaymentResponse create(UUID bookingId,UUID patientIdentityId,String recipientEmail){
  String normalizedEmail=recipientEmail==null||recipientEmail.isBlank()?null:recipientEmail.trim().toLowerCase(Locale.ROOT);
  var old=payments.findByBookingIdAndPatientIdentityId(bookingId,patientIdentityId);
  if(old.isPresent()&&old.get().status!=PaymentStatus.FAILED)return response(old.get());
  Payment payment;
  if(old.isPresent())payment=old.get();
  else{
   var booking=bookings.preparePayment(bookingId,patientIdentityId);
   if(!patientIdentityId.equals(booking.patientIdentityId()))throw new PaymentForbidden();
   try{
    payment=tx.execute(status->{
     var concurrent=payments.findByBookingId(bookingId);if(concurrent.isPresent())return concurrent.get();
     var now=clock.instant();
     return payments.saveAndFlush(Payment.creating(bookingId,patientIdentityId,deposit,orderCodes.next(),booking.startAt(),now.plus(holdDuration),now,normalizedEmail));
    });
   }catch(DataIntegrityViolationException race){payment=payments.findByBookingId(bookingId).orElseThrow(()->race);}
  }
  if(payment.status!=PaymentStatus.CREATING&&payment.status!=PaymentStatus.FAILED)return response(payment);
  try{
   var link=payOS.create(payment.orderCode,payment.amount.longValueExact(),"DERMAI "+payment.orderCode,returnUrl,cancelUrl,payment.expiresAt);
   UUID id=payment.id;
   return tx.execute(status->{
    var current=payments.findById(id).orElseThrow(PaymentNotFound::new);
    if(current.status==PaymentStatus.SUCCESS)return response(current);
    current.paymentLinkId=link.paymentLinkId();current.checkoutUrl=link.checkoutUrl();current.qrCode=link.qrCode();
    current.status=PaymentStatus.PENDING;current.updatedAt=clock.instant();payments.save(current);
    if(current.recipientEmail!=null)addEvent(current,"payment.link_created","PAYMENT_PENDING");
    return response(current);
   });
  }catch(RuntimeException failure){
   UUID id=payment.id;tx.executeWithoutResult(status->payments.findById(id).ifPresent(current->{if(current.status==PaymentStatus.CREATING)current.status=PaymentStatus.FAILED;current.updatedAt=clock.instant();}));
   throw new PaymentProviderException(failure);
  }
 }

 public PaymentResponse get(UUID bookingId,UUID patientIdentityId){return payments.findByBookingIdAndPatientIdentityId(bookingId,patientIdentityId).map(this::response).orElseThrow(PaymentNotFound::new);}
 public PaymentResponse getForStaff(UUID bookingId){return payments.findByBookingId(bookingId).map(this::response).orElseThrow(PaymentNotFound::new);}

 public boolean handleWebhook(Map<String,Object> payload){
  final PayOSGateway.VerifiedWebhook data;
  try{data=payOS.verify(payload);}catch(RuntimeException invalid){throw new InvalidWebhookException(invalid);}
  if(!"00".equals(data.code()))return false;
  return confirmPaid(data.orderCode(),data.amount(),data.reference(),data.paymentLinkId());
 }

 public PaymentResponse reconcile(long orderCode,UUID actorIdentityId,String actorRole){return reconcile(orderCode,actorIdentityId,actorRole,true);}
 public PaymentResponse reconcile(long orderCode){return reconcile(orderCode,null,"SYSTEM",false);}
 private PaymentResponse reconcile(long orderCode,UUID actorIdentityId,String actorRole,boolean enforceAccess){
  var claim=tx.execute(status->{
   var payment=payments.findByOrderCode(orderCode).orElseThrow(PaymentNotFound::new);
   if(enforceAccess&&"PATIENT".equals(actorRole)&&!payment.patientIdentityId.equals(actorIdentityId))throw new PaymentForbidden();
   if(enforceAccess&&!Set.of("PATIENT","RECEPTIONIST","ADMIN").contains(actorRole))throw new PaymentForbidden();
   return new ReconciliationClaim(payment.id,payment.orderCode,payment.amount,payment.paymentLinkId,payment.status);
  });
  if(claim.status()==PaymentStatus.SUCCESS)return tx.execute(status->response(payments.findById(claim.id()).orElseThrow(PaymentNotFound::new)));
  final PayOSGateway.PaymentLinkStatusResult provider;
  try{provider=payOS.get(orderCode);}catch(RuntimeException failure){throw new PaymentProviderException(failure);}
  if("PAID".equals(provider.status())){
   if(provider.amount()!=claim.amount().longValueExact()||provider.amountPaid()<claim.amount().longValueExact())throw new WebhookMismatchException("AMOUNT_MISMATCH");
   if(claim.paymentLinkId()!=null&&!claim.paymentLinkId().equals(provider.paymentLinkId()))throw new WebhookMismatchException("PAYMENT_LINK_MISMATCH");
   confirmPaid(orderCode,provider.amount(),provider.reference(),provider.paymentLinkId());
  }
  return tx.execute(status->response(payments.findByOrderCode(orderCode).orElseThrow(PaymentNotFound::new)));
 }

 private boolean confirmPaid(long orderCode,long amount,String reference,String paymentLinkId){
  return Boolean.TRUE.equals(tx.execute(status->{
   var payment=payments.findByOrderCode(orderCode).orElse(null);
   if(payment==null)return false;
   if(payment.amount.longValueExact()!=amount)throw new WebhookMismatchException("AMOUNT_MISMATCH");
   if(payment.paymentLinkId!=null&&!payment.paymentLinkId.equals(paymentLinkId))throw new WebhookMismatchException("PAYMENT_LINK_MISMATCH");
   if(payment.status==PaymentStatus.SUCCESS)return true;
   if(EnumSet.of(PaymentStatus.EXPIRED,PaymentStatus.CANCELLED,PaymentStatus.REFUND_REQUESTED,PaymentStatus.REFUNDED).contains(payment.status))throw new WebhookMismatchException("PAYMENT_ALREADY_CLOSED");
   payment.status=PaymentStatus.SUCCESS;payment.payosTransId=reference;payment.paymentLinkId=paymentLinkId;payment.updatedAt=clock.instant();
   payments.save(payment);addEvent(payment,"booking.paid","CONFIRMED");return true;
  }));
 }
 public PaymentResponse cancel(long orderCode,UUID patientIdentityId){
  var claim=tx.execute(status->{
   var payment=payments.findByOrderCode(orderCode).orElseThrow(PaymentNotFound::new);
   if(!patientIdentityId.equals(payment.patientIdentityId))throw new PaymentForbidden();
   if(payment.status==PaymentStatus.SUCCESS)throw new PaymentConflict("PAYMENT_ALREADY_SUCCESS");
   if(EnumSet.of(PaymentStatus.CANCELLED,PaymentStatus.EXPIRED,PaymentStatus.CANCEL_REQUESTED).contains(payment.status))
    return new ManualCancelClaim(payment.id,payment.orderCode,payment.status,false);
   var previous=payment.status;payment.status=PaymentStatus.CANCEL_REQUESTED;payment.updatedAt=clock.instant();payments.save(payment);
   return new ManualCancelClaim(payment.id,payment.orderCode,previous,true);
  });
  if(!claim.shouldCancel())return payments.findById(claim.id()).map(this::response).orElseThrow(PaymentNotFound::new);
  try{payOS.cancel(claim.orderCode(),"Patient cancelled payment");}
  catch(RuntimeException failure){
   tx.executeWithoutResult(status->payments.findById(claim.id()).ifPresent(payment->{if(payment.status==PaymentStatus.CANCEL_REQUESTED){payment.status=claim.previousStatus();payment.updatedAt=clock.instant();}}));
   throw new PaymentProviderException(failure);
  }
  return tx.execute(status->{
   var payment=payments.findById(claim.id()).orElseThrow(PaymentNotFound::new);
   if(payment.status==PaymentStatus.CANCEL_REQUESTED){payment.status=PaymentStatus.CANCELLED;payment.updatedAt=clock.instant();payments.save(payment);addEvent(payment,"booking.payment_cancelled","CANCELLED");}
   return response(payment);
  });
 }

 public PaymentResponse requestPatientRefund(UUID bookingId,UUID patientIdentityId,String requestedReason){
  var booking=bookings.get(bookingId);
  if(!patientIdentityId.equals(booking.patientIdentityId()))throw new PaymentForbidden();
  if(!"CANCELLED".equals(booking.status()))throw new PaymentConflict("APPOINTMENT_NOT_CANCELLED");
  if(!"PATIENT_REQUEST".equals(booking.cancellationInitiator()))throw new PaymentConflict("PATIENT_REFUND_REQUEST_NOT_ALLOWED");
  var reason=requestedReason==null||requestedReason.isBlank()?booking.cancelReason():requestedReason.trim();
  if(reason==null||reason.isBlank())reason="Bệnh nhân yêu cầu hoàn tiền cọc sau khi hủy lịch";
  if(reason.length()>500)throw new PaymentConflict("REFUND_REASON_TOO_LONG");
  var refundReason=reason;
  return tx.execute(status->{
   var payment=payments.findLockedByBookingId(bookingId).orElseThrow(PaymentNotFound::new);
   if(!patientIdentityId.equals(payment.patientIdentityId))throw new PaymentForbidden();
   if(EnumSet.of(PaymentStatus.REFUND_REQUESTED,PaymentStatus.REFUNDED).contains(payment.status))return response(payment);
   if(payment.status!=PaymentStatus.SUCCESS)throw new PaymentConflict("PAYMENT_NOT_REFUNDABLE");
   var now=clock.instant();var eligibleAmount=patientRefundAmount(payment,now);
   if(eligibleAmount.signum()<=0)throw new PaymentConflict("REFUND_NOT_ELIGIBLE_UNDER_6_HOURS");
   payment.status=PaymentStatus.REFUND_REQUESTED;payment.refundReason=refundReason;payment.refundRequestedByIdentity=patientIdentityId;payment.refundRequestedByRole="PATIENT";
   payment.refundInitiator="PATIENT_REQUEST";payment.refundRequestedAt=now;payment.refundAmount=eligibleAmount;payment.updatedAt=now;
   payments.save(payment);addEvent(payment,"payment.refund_requested","REFUND_REQUESTED");return response(payment);
  });
 }
 private BigDecimal patientRefundAmount(Payment payment,Instant requestedAt){
  if(!requestedAt.isAfter(payment.createdAt.plus(Duration.ofMinutes(30))))return payment.amount;
  var untilAppointment=Duration.between(requestedAt,payment.appointmentStartAt);
  if(untilAppointment.compareTo(Duration.ofHours(24))>=0)return payment.amount;
  if(untilAppointment.compareTo(Duration.ofHours(6))>=0)return payment.amount.divide(new BigDecimal("2"),0,java.math.RoundingMode.DOWN);
  return BigDecimal.ZERO;
 }
 public Optional<PaymentResponse> requestRefund(UUID bookingId,UUID actorIdentityId,String actorRole,String initiator,String reason){
  return tx.execute(status->{
   var payment=payments.findLockedByBookingId(bookingId).orElse(null);if(payment==null)return Optional.empty();
   if(EnumSet.of(PaymentStatus.REFUND_REQUESTED,PaymentStatus.REFUNDED).contains(payment.status))return Optional.of(response(payment));
   if(payment.status!=PaymentStatus.SUCCESS)return Optional.empty();
   payment.status=PaymentStatus.REFUND_REQUESTED;payment.refundReason=reason;payment.refundRequestedByIdentity=actorIdentityId;payment.refundRequestedByRole=actorRole;
   payment.refundInitiator="CLINIC".equals(initiator)?"CLINIC":"PATIENT_REQUEST";payment.refundRequestedAt=clock.instant();payment.updatedAt=clock.instant();
   if("CLINIC".equals(payment.refundInitiator))payment.refundAmount=payment.amount;
   payments.save(payment);addEvent(payment,"payment.refund_requested","REFUND_REQUESTED");return Optional.of(response(payment));
  });
 }

 public List<PaymentResponse> refunds(){return payments.findTop100ByStatusInOrderByRefundRequestedAtDesc(EnumSet.of(PaymentStatus.REFUND_REQUESTED,PaymentStatus.REFUNDED)).stream().map(this::response).toList();}
 public List<PaymentResponse> all(){return payments.findAll().stream().sorted(Comparator.comparing((Payment p)->p.createdAt).reversed()).limit(500).map(this::response).toList();}

 public PaymentResponse completeRefund(UUID paymentId,BigDecimal amount,String method,String reference,String recipientName,RefundEvidence evidence,UUID actorIdentityId,String actorRole){
  if(!"RECEPTIONIST".equals(actorRole))throw new PaymentForbidden();
  return tx.execute(status->{
   var payment=payments.findById(paymentId).orElseThrow(PaymentNotFound::new);
   if(payment.status==PaymentStatus.REFUNDED)return response(payment);
   if(payment.status!=PaymentStatus.REFUND_REQUESTED)throw new PaymentConflict("REFUND_NOT_REQUESTED");
   if(amount==null||amount.signum()<=0||amount.compareTo(payment.amount)>0)throw new PaymentConflict("INVALID_REFUND_AMOUNT");
   var policyAmount="CLINIC".equals(payment.refundInitiator)?payment.amount:payment.refundAmount;
   if(policyAmount==null)policyAmount=patientRefundAmount(payment,payment.refundRequestedAt==null?clock.instant():payment.refundRequestedAt);
   if(policyAmount.signum()<=0)throw new PaymentConflict("REFUND_NOT_ELIGIBLE_UNDER_6_HOURS");
   if(amount.compareTo(policyAmount)!=0)throw new PaymentConflict("REFUND_AMOUNT_MUST_MATCH_POLICY");
   var normalizedMethod=method==null?"":method.trim().toUpperCase(Locale.ROOT);if(!Set.of("BANK_TRANSFER","CASH").contains(normalizedMethod))throw new PaymentConflict("INVALID_REFUND_METHOD");
   var normalizedReference=reference==null||reference.isBlank()?null:reference.trim();var normalizedRecipient=recipientName==null||recipientName.isBlank()?null:recipientName.trim();
   if("BANK_TRANSFER".equals(normalizedMethod)&&normalizedReference==null&&evidence==null)throw new PaymentConflict("REFUND_TRANSFER_PROOF_REQUIRED");
   if("CASH".equals(normalizedMethod)&&normalizedRecipient==null)throw new PaymentConflict("REFUND_CASH_RECIPIENT_REQUIRED");
   if(evidence!=null&&(evidence.data()==null||evidence.data().length==0||evidence.data().length>5L*1024*1024||!Set.of("image/jpeg","image/png","image/webp").contains(evidence.contentType())))throw new PaymentConflict("INVALID_REFUND_EVIDENCE");
   payment.refundAmount=amount;payment.refundMethod=normalizedMethod;payment.refundReference=normalizedReference;payment.refundRecipientName=normalizedRecipient;
   payment.refundReceiptNumber="CASH".equals(normalizedMethod)?cashReceiptNumber(payment):null;
   if(evidence!=null){payment.refundEvidenceContentType=evidence.contentType();payment.refundEvidenceOriginalName=evidence.originalName();payment.refundEvidenceSizeBytes=(long)evidence.data().length;payment.refundEvidenceData=evidence.data().clone();}
   payment.refundedAt=clock.instant();payment.refundCompletedByIdentity=actorIdentityId;payment.refundCompletedByRole=actorRole;payment.status=PaymentStatus.REFUNDED;payment.updatedAt=clock.instant();
   payments.save(payment);addEvent(payment,"payment.refunded","REFUNDED");return response(payment);
  });
 }
 public RefundEvidenceData refundEvidence(UUID paymentId){var payment=payments.findUnlockedById(paymentId).orElseThrow(PaymentNotFound::new);if(payment.refundEvidenceData==null)throw new PaymentNotFound();return new RefundEvidenceData(payment.refundEvidenceContentType,payment.refundEvidenceOriginalName,payment.refundEvidenceData.clone());}
 private String cashReceiptNumber(Payment payment){var date=LocalDate.ofInstant(clock.instant(),ZoneId.of("Asia/Ho_Chi_Minh")).toString().replace("-","");return "HT-"+date+"-"+payment.orderCode;}
 public void expire(UUID paymentId){
  var claim=tx.execute(status->{
   var payment=payments.findById(paymentId).orElse(null);
   if(payment==null||!EnumSet.of(PaymentStatus.CREATING,PaymentStatus.PENDING,PaymentStatus.FAILED).contains(payment.status)||payment.expiresAt.isAfter(clock.instant()))return null;
   payment.status=PaymentStatus.CANCEL_REQUESTED;payment.updatedAt=clock.instant();payments.save(payment);
   return new ExpiryClaim(payment.id,payment.orderCode);
  });
  if(claim==null)return;
  try{payOS.cancel(claim.orderCode(),"Payment hold expired after 10 minutes");}
  catch(RuntimeException failure){
   tx.executeWithoutResult(status->payments.findById(claim.id()).ifPresent(payment->{if(payment.status==PaymentStatus.CANCEL_REQUESTED){payment.status=PaymentStatus.PENDING;payment.updatedAt=clock.instant();}}));
   throw new PaymentProviderException(failure);
  }
  tx.executeWithoutResult(status->payments.findById(claim.id()).ifPresent(payment->{
   if(payment.status==PaymentStatus.CANCEL_REQUESTED){payment.status=PaymentStatus.EXPIRED;payment.updatedAt=clock.instant();payments.save(payment);addEvent(payment,"booking.payment_expired","CANCELLED_EXPIRED");}
  }));
 }

 private record ReconciliationClaim(UUID id,long orderCode,BigDecimal amount,String paymentLinkId,PaymentStatus status){}
 private record ManualCancelClaim(UUID id,long orderCode,PaymentStatus previousStatus,boolean shouldCancel){}
 private record ExpiryClaim(UUID id,long orderCode){}

 private void addEvent(Payment payment,String routingKey,String bookingStatus){
  var now=clock.instant();var event=new PaymentOutboxEvent(payment.id,routingKey,"{}",now);var body=new LinkedHashMap<String,Object>();
  body.put("eventId",event.id);body.put("paymentId",payment.id);body.put("bookingId",payment.bookingId);body.put("patientIdentityId",payment.patientIdentityId);
  body.put("status",bookingStatus);body.put("startAt",payment.appointmentStartAt);body.put("amount",payment.amount);body.put("orderCode",payment.orderCode);body.put("payosTransId",payment.payosTransId);body.put("occurredAt",now);
  if(payment.recipientEmail!=null)body.put("recipientEmail",payment.recipientEmail);
  if(payment.checkoutUrl!=null)body.put("checkoutUrl",payment.checkoutUrl);
  if(payment.expiresAt!=null)body.put("expiresAt",payment.expiresAt);if(payment.refundReason!=null)body.put("refundReason",payment.refundReason);if(payment.refundInitiator!=null)body.put("refundInitiator",payment.refundInitiator);if(payment.refundAmount!=null)body.put("refundAmount",payment.refundAmount);if(payment.refundReference!=null)body.put("refundReference",payment.refundReference);if(payment.refundMethod!=null)body.put("refundMethod",payment.refundMethod);if(payment.refundReceiptNumber!=null)body.put("refundReceiptNumber",payment.refundReceiptNumber);if(payment.refundRecipientName!=null)body.put("refundRecipientName",payment.refundRecipientName);
  try{event.payload=json.writeValueAsString(body);}catch(JsonProcessingException impossible){throw new IllegalStateException(impossible);}
  outbox.save(event);
 }

 public record RefundEvidence(String contentType,String originalName,byte[] data){}
 public record RefundEvidenceData(String contentType,String originalName,byte[] data){}
 public record PaymentResponse(UUID id,UUID bookingId,BigDecimal amount,long orderCode,PaymentStatus status,String checkoutUrl,String qrCode,Instant expiresAt,Instant createdAt,String recipientEmail,String refundReason,UUID refundRequestedByIdentity,String refundRequestedByRole,String refundInitiator,Instant refundRequestedAt,BigDecimal refundAmount,Instant refundedAt,String refundReference,UUID refundCompletedByIdentity,String refundCompletedByRole,String refundMethod,String refundReceiptNumber,String refundRecipientName,boolean refundEvidenceAvailable,String refundEvidenceOriginalName){}
 private PaymentResponse response(Payment p){return new PaymentResponse(p.id,p.bookingId,p.amount,p.orderCode,p.status,p.checkoutUrl,p.qrCode,p.expiresAt,p.createdAt,p.recipientEmail,p.refundReason,p.refundRequestedByIdentity,p.refundRequestedByRole,p.refundInitiator,p.refundRequestedAt,p.refundAmount,p.refundedAt,p.refundReference,p.refundCompletedByIdentity,p.refundCompletedByRole,p.refundMethod,p.refundReceiptNumber,p.refundRecipientName,p.refundEvidenceData!=null,p.refundEvidenceOriginalName);}
}
