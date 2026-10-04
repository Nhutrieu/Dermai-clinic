package com.dermai.prescription;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.time.Clock;
import java.util.LinkedHashMap;
import java.util.UUID;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.stereotype.Component;
import org.springframework.transaction.support.TransactionSynchronization;
import org.springframework.transaction.support.TransactionSynchronizationManager;

@Component
class BillingReceptionEvents {
 private static final String EXCHANGE = "booking_events";
 private final RabbitTemplate rabbit;
 private final ObjectMapper json;
 private final Clock clock;

 BillingReceptionEvents(RabbitTemplate rabbit, ObjectMapper json, Clock clock) {
  this.rabbit = rabbit;
  this.json = json;
  this.clock = clock;
 }

 void created(Invoice invoice) { publish("billing.invoice.created", "CREATED", invoice); }
 void paid(Invoice invoice) { publish("billing.invoice.paid", "PAID", invoice); }

 private void publish(String routingKey, String status, Invoice invoice) {
  try {
   var body = new LinkedHashMap<String, Object>();
   body.put("eventId", UUID.randomUUID());
   body.put("invoiceId", invoice.id);
   body.put("appointmentId", invoice.appointmentId);
   body.put("patientIdentityId", invoice.patientIdentityId);
   body.put("status", status);
   body.put("totalAmount", invoice.totalAmount);
   body.put("remainingAmount", invoice.remainingAmount);
   body.put("occurredAt", clock.instant());
   var payload = json.writeValueAsString(body);
   var send = (Runnable) () -> rabbit.convertAndSend(EXCHANGE, routingKey, payload);
   if (TransactionSynchronizationManager.isSynchronizationActive()) {
    TransactionSynchronizationManager.registerSynchronization(new TransactionSynchronization() {
     @Override public void afterCommit() { send.run(); }
    });
   } else send.run();
  } catch (Exception error) {
   throw new IllegalStateException("Cannot publish billing reception event", error);
  }
 }
}
