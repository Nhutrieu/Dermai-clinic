package com.dermai.payment;

import java.time.Instant;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;

@Component
@ConditionalOnProperty(name="payos.fake-mode",havingValue="true")
class FakePayOSGateway implements PayOSGateway{
 private final Map<Long,FakePayment> payments=new ConcurrentHashMap<>();

 @Override public PaymentLinkResult create(long orderCode,long amount,String description,String returnUrl,String cancelUrl,Instant expiresAt){
  var payment=new FakePayment("e2e-"+orderCode,amount,"PAID","E2E-"+orderCode);
  payments.put(orderCode,payment);
  var separator=returnUrl.contains("?")?"&":"?";
  return new PaymentLinkResult(payment.paymentLinkId(),returnUrl+separator+"orderCode="+orderCode+"&status=PAID","E2E_FAKE_QR");
 }

 @Override public VerifiedWebhook verify(Map<String,Object> payload){
  var orderCode=Long.parseLong(String.valueOf(payload.get("orderCode")));
  var payment=required(orderCode);
  return new VerifiedWebhook(orderCode,payment.amount(),payment.reference(),payment.paymentLinkId(),"00");
 }

 @Override public PaymentLinkStatusResult get(long orderCode){
  var payment=required(orderCode);
  var paid="PAID".equals(payment.status())?payment.amount():0L;
  return new PaymentLinkStatusResult(payment.paymentLinkId(),payment.amount(),paid,payment.status(),payment.reference());
 }

 @Override public void confirmWebhook(String webhookUrl){/* No external callback is needed in isolated E2E mode. */}

 @Override public void cancel(long orderCode,String reason){
  payments.computeIfPresent(orderCode,(ignored,payment)->new FakePayment(payment.paymentLinkId(),payment.amount(),"CANCELLED",payment.reference()));
 }

 private FakePayment required(long orderCode){
  var payment=payments.get(orderCode);
  if(payment==null)throw new IllegalArgumentException("Unknown fake PayOS order: "+orderCode);
  return payment;
 }

 private record FakePayment(String paymentLinkId,long amount,String status,String reference){}
}
