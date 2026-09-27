package com.dermai.payment;
import java.time.Instant;
import java.util.Map;
interface PayOSGateway{
 PaymentLinkResult create(long orderCode,long amount,String description,String returnUrl,String cancelUrl,Instant expiresAt);
 VerifiedWebhook verify(Map<String,Object> payload);
 PaymentLinkStatusResult get(long orderCode);
 void confirmWebhook(String webhookUrl);
 void cancel(long orderCode,String reason);
 record PaymentLinkResult(String paymentLinkId,String checkoutUrl,String qrCode){}
 record VerifiedWebhook(long orderCode,long amount,String reference,String paymentLinkId,String code){}
 record PaymentLinkStatusResult(String paymentLinkId,long amount,long amountPaid,String status,String reference){}
}