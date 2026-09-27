package com.dermai.payment;
import java.time.Clock;
import java.util.EnumSet;
import org.slf4j.*;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

@Component class PaymentExpiryScheduler{
 private static final Logger log=LoggerFactory.getLogger(PaymentExpiryScheduler.class);
 private final PaymentRepository payments;private final PaymentService service;private final Clock clock;
 PaymentExpiryScheduler(PaymentRepository payments,PaymentService service,Clock clock){this.payments=payments;this.service=service;this.clock=clock;}
 @Scheduled(initialDelay=15000,fixedDelayString="${payment.expiry-delay-ms:15000}")
 public void expire(){
  for(var payment:payments.findTop100ByStatusInOrderByUpdatedAtAsc(EnumSet.of(PaymentStatus.PENDING))){
   try{service.reconcile(payment.orderCode);}
   catch(PaymentProviderException failure){log.warn("Could not reconcile payOS order {}. It will be retried.",payment.orderCode,failure);}
   catch(WebhookMismatchException mismatch){log.error("payOS reconciliation mismatch for order {}: {}",payment.orderCode,mismatch.getMessage());}
  }
  for(var payment:payments.findTop100ByStatusInAndExpiresAtLessThanEqualOrderByExpiresAtAsc(EnumSet.of(PaymentStatus.CREATING,PaymentStatus.PENDING,PaymentStatus.FAILED),clock.instant())){
   try{service.expire(payment.id);}
   catch(PaymentProviderException failure){log.warn("Could not cancel expired payOS order {}. It will be retried.",payment.orderCode,failure);}
  }
 }
}