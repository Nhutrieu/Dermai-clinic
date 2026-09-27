package com.dermai.payment;
import java.time.Instant;
import java.util.Map;
import org.springframework.stereotype.Component;
import vn.payos.PayOS;
import vn.payos.exception.NotFoundException;
import vn.payos.model.v2.paymentRequests.CreatePaymentLinkRequest;

@Component class PayOSClientAdapter implements PayOSGateway{
 private final PayOS payOS;
 PayOSClientAdapter(PayOS payOS){this.payOS=payOS;}

 @Override public PaymentLinkResult create(long orderCode,long amount,String description,String returnUrl,String cancelUrl,Instant expiresAt){
  var request=CreatePaymentLinkRequest.builder()
    .orderCode(orderCode)
    .amount(amount)
    .description(description)
    .returnUrl(returnUrl)
    .cancelUrl(cancelUrl)
    .expiredAt(expiresAt.getEpochSecond())
    .build();
  var response=payOS.paymentRequests().create(request);
  return new PaymentLinkResult(response.getPaymentLinkId(),response.getCheckoutUrl(),response.getQrCode());
 }

 @Override public VerifiedWebhook verify(Map<String,Object> payload){
  var data=payOS.webhooks().verify(payload);
  return new VerifiedWebhook(data.getOrderCode(),data.getAmount(),data.getReference(),data.getPaymentLinkId(),data.getCode());
 }

 @Override public PaymentLinkStatusResult get(long orderCode){
  var payment=payOS.paymentRequests().get(orderCode);
  var reference=payment.getTransactions()==null?null:payment.getTransactions().stream()
    .filter(transaction->transaction.getReference()!=null&&!transaction.getReference().isBlank())
    .map(transaction->transaction.getReference()).findFirst().orElse(null);
  return new PaymentLinkStatusResult(payment.getId(),value(payment.getAmount()),value(payment.getAmountPaid()),payment.getStatus().name(),reference);
 }

 @Override public void confirmWebhook(String webhookUrl){payOS.webhooks().confirm(webhookUrl);}

 @Override public void cancel(long orderCode,String reason){
  try{payOS.paymentRequests().cancel(orderCode,reason);}catch(NotFoundException alreadyAbsent){/* Local expiry may continue when no link was created. */}
 }

 private long value(Long amount){return amount==null?0L:amount;}
}