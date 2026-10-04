package com.dermai.payment;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.math.BigDecimal;
import java.time.*;
import java.util.*;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class InvoicePaymentService {
 private final InvoicePaymentRepository payments;private final PaymentOutboxRepository outbox;private final OrderCodeGenerator codes;private final PayOSGateway gateway;private final ObjectMapper json;private final Clock clock;private final String returnUrl;private final String cancelUrl;
 InvoicePaymentService(InvoicePaymentRepository payments,PaymentOutboxRepository outbox,OrderCodeGenerator codes,PayOSGateway gateway,ObjectMapper json,Clock clock,@Value("${payment.invoice-return-url:${payment.return-url}}")String returnUrl,@Value("${payment.invoice-cancel-url:${payment.cancel-url}}")String cancelUrl){this.payments=payments;this.outbox=outbox;this.codes=codes;this.gateway=gateway;this.json=json;this.clock=clock;this.returnUrl=returnUrl;this.cancelUrl=cancelUrl;}
 @Transactional public Response create(UUID invoiceId,UUID patientIdentityId,BigDecimal amount){
  if(amount==null||amount.signum()<=0)throw new PaymentConflict("INVALID_INVOICE_AMOUNT");
  var existing=payments.findByInvoiceId(invoiceId);if(existing.isPresent()&&!EnumSet.of(PaymentStatus.FAILED,PaymentStatus.EXPIRED,PaymentStatus.CANCELLED).contains(existing.get().status))return response(existing.get());
  var payment=existing.orElseGet(InvoicePayment::new);var now=clock.instant();payment.id=payment.id==null?UUID.randomUUID():payment.id;payment.invoiceId=invoiceId;payment.patientIdentityId=patientIdentityId;payment.amount=amount;payment.orderCode=codes.next();payment.status=PaymentStatus.CREATING;payment.createdAt=payment.createdAt==null?now:payment.createdAt;payment.updatedAt=now;payment.expiresAt=now.plus(Duration.ofMinutes(30));payments.save(payment);
  try{var link=gateway.create(payment.orderCode,amount.longValueExact(),"DERMAI HD "+payment.orderCode,returnUrl,cancelUrl,payment.expiresAt);payment.paymentLinkId=link.paymentLinkId();payment.checkoutUrl=link.checkoutUrl();payment.qrCode=link.qrCode();payment.status=PaymentStatus.PENDING;payment.updatedAt=clock.instant();return response(payments.save(payment));}
  catch(RuntimeException error){payment.status=PaymentStatus.FAILED;payment.updatedAt=clock.instant();payments.save(payment);throw new PaymentProviderException(error);}
 }
 @Transactional public boolean handleWebhook(Map<String,Object> payload){
  final PayOSGateway.VerifiedWebhook data;try{data=gateway.verify(payload);}catch(RuntimeException invalid){throw new InvalidWebhookException(invalid);}
  if(!"00".equals(data.code()))return false;var payment=payments.findByOrderCode(data.orderCode()).orElse(null);if(payment==null)return false;
  if(payment.amount.longValueExact()!=data.amount())throw new WebhookMismatchException("AMOUNT_MISMATCH");if(payment.paymentLinkId!=null&&!payment.paymentLinkId.equals(data.paymentLinkId()))throw new WebhookMismatchException("PAYMENT_LINK_MISMATCH");if(payment.status==PaymentStatus.SUCCESS)return true;if(payment.status==PaymentStatus.EXPIRED)throw new WebhookMismatchException("PAYMENT_ALREADY_EXPIRED");
  payment.status=PaymentStatus.SUCCESS;payment.payosTransId=data.reference();payment.paymentLinkId=data.paymentLinkId();payment.updatedAt=clock.instant();payments.save(payment);publishPaid(payment);return true;
 }
 @Transactional public Response reconcile(long orderCode){return reconcile(payments.findByOrderCode(orderCode).orElseThrow(PaymentNotFound::new));}
 @Transactional public Response reconcile(long orderCode,UUID actorIdentityId,String actorRole){return reconcile(authorized(orderCode,actorIdentityId,actorRole));}
 private Response reconcile(InvoicePayment payment){
  if(payment.status==PaymentStatus.SUCCESS)return response(payment);var orderCode=payment.orderCode;
  final PayOSGateway.PaymentLinkStatusResult provider;try{provider=gateway.get(orderCode);}catch(RuntimeException failure){throw new PaymentProviderException(failure);}
  if("PAID".equals(provider.status())){
   if(provider.amount()!=payment.amount.longValueExact()||provider.amountPaid()<payment.amount.longValueExact())throw new WebhookMismatchException("AMOUNT_MISMATCH");
   if(payment.paymentLinkId!=null&&!payment.paymentLinkId.equals(provider.paymentLinkId()))throw new WebhookMismatchException("PAYMENT_LINK_MISMATCH");
   payment.status=PaymentStatus.SUCCESS;payment.payosTransId=provider.reference();payment.paymentLinkId=provider.paymentLinkId();payment.updatedAt=clock.instant();payments.save(payment);publishPaid(payment);
  }else if(Set.of("CANCELLED","EXPIRED").contains(provider.status())){payment.status="EXPIRED".equals(provider.status())?PaymentStatus.EXPIRED:PaymentStatus.CANCELLED;payment.updatedAt=clock.instant();payments.save(payment);}
  return response(payment);
 }
 @Transactional public Response cancel(long orderCode,UUID actorIdentityId,String actorRole){
  var payment=authorized(orderCode,actorIdentityId,actorRole);if(payment.status==PaymentStatus.SUCCESS)throw new PaymentConflict("PAYMENT_ALREADY_PAID");
  if(payment.status==PaymentStatus.CANCELLED||payment.status==PaymentStatus.EXPIRED)return response(payment);
  try{gateway.cancel(orderCode,"Patient cancelled invoice payment");}catch(RuntimeException failure){throw new PaymentProviderException(failure);}
  payment.status=PaymentStatus.CANCELLED;payment.updatedAt=clock.instant();return response(payments.save(payment));
 }
 private InvoicePayment authorized(long orderCode,UUID actorIdentityId,String actorRole){var payment=payments.findByOrderCode(orderCode).orElseThrow(PaymentNotFound::new);if("PATIENT".equals(actorRole)&&!payment.patientIdentityId.equals(actorIdentityId))throw new PaymentForbidden();if(!Set.of("PATIENT","RECEPTIONIST","ADMIN").contains(actorRole))throw new PaymentForbidden();return payment;}
 private void publishPaid(InvoicePayment payment){try{var now=clock.instant();var event=new PaymentOutboxEvent(payment.id,"invoice.paid","{}",now);var body=new LinkedHashMap<String,Object>();body.put("eventId",event.id);body.put("invoiceId",payment.invoiceId);body.put("paymentId",payment.id);body.put("patientIdentityId",payment.patientIdentityId);body.put("amount",payment.amount);body.put("orderCode",payment.orderCode);body.put("payosTransId",payment.payosTransId);body.put("occurredAt",now);event.payload=json.writeValueAsString(body);outbox.save(event);}catch(Exception error){throw new IllegalStateException(error);}}
 public record Response(UUID id,UUID invoiceId,BigDecimal amount,long orderCode,PaymentStatus status,String checkoutUrl,String qrCode,Instant expiresAt,String payosTransId){}
 private Response response(InvoicePayment p){return new Response(p.id,p.invoiceId,p.amount,p.orderCode,p.status,p.checkoutUrl,p.qrCode,p.expiresAt,p.payosTransId);}
}
