package com.dermai.appointment;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.text.NumberFormat;
import java.util.Locale;
import java.util.UUID;
import org.springframework.amqp.core.Binding;
import org.springframework.amqp.core.BindingBuilder;
import org.springframework.amqp.core.Queue;
import org.springframework.amqp.core.QueueBuilder;
import org.springframework.amqp.core.TopicExchange;
import org.springframework.amqp.rabbit.annotation.RabbitListener;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.stereotype.Component;

@Configuration
class BillingReceptionNotificationMessaging {
 @Bean Queue receptionBillingNotificationQueue() { return QueueBuilder.durable("dermai.reception-billing-notifications").build(); }
 @Bean Binding invoiceCreatedReceptionBinding(@Qualifier("receptionBillingNotificationQueue") Queue queue, @Qualifier("bookingEventsExchange") TopicExchange exchange) { return BindingBuilder.bind(queue).to(exchange).with("billing.invoice.created"); }
 @Bean Binding invoicePaidReceptionBinding(@Qualifier("receptionBillingNotificationQueue") Queue queue, @Qualifier("bookingEventsExchange") TopicExchange exchange) { return BindingBuilder.bind(queue).to(exchange).with("billing.invoice.paid"); }
}

@Component
class BillingReceptionNotificationConsumer {
 private final ReceptionNotificationRepository notifications;
 private final SlotUpdateBroadcaster updates;
 private final ObjectMapper json;

 BillingReceptionNotificationConsumer(ReceptionNotificationRepository notifications, SlotUpdateBroadcaster updates, ObjectMapper json) {
  this.notifications = notifications;
  this.updates = updates;
  this.json = json;
 }

 @RabbitListener(queues = "dermai.reception-billing-notifications")
 public void consume(String payload) throws Exception {
  var event = json.readTree(payload);
  var appointmentId = requiredUuid(event, "appointmentId");
  var patientIdentityId = requiredUuid(event, "patientIdentityId");
  var invoiceId = requiredUuid(event, "invoiceId");
  var paid = "PAID".equals(event.path("status").asText());
  var type = paid ? "INVOICE_PAID" : "INVOICE_CREATED";
  if (notifications.existsByAppointmentIdAndNotificationType(appointmentId, type)) return;

  var total = money(event.path("totalAmount"));
  var remaining = money(event.path("remainingAmount"));
  var code = invoiceId.toString().substring(0, 8).toUpperCase(Locale.ROOT);
  var title = paid ? "Hóa đơn đã thanh toán" : "Có hóa đơn mới";
  var body = paid
    ? "Hóa đơn #" + code + " đã thanh toán đủ " + total + ". Sẵn sàng chuyển sang bước tiếp theo."
    : "Hóa đơn #" + code + " có tổng tiền " + total + (event.path("remainingAmount").decimalValue().signum() == 0
      ? " và đã được thanh toán đủ bằng tiền cọc."
      : ", còn " + remaining + " cần thu. Vui lòng theo dõi thanh toán.");
  notifications.save(new ReceptionNotification(appointmentId, patientIdentityId, type, title, body));
  updates.receptionNotificationsChanged();
 }

 private UUID requiredUuid(JsonNode event, String field) {
  var value = event.path(field).asText();
  if (value.isBlank()) throw new IllegalArgumentException("Missing billing event field: " + field);
  return UUID.fromString(value);
 }

 private String money(JsonNode value) {
  return NumberFormat.getIntegerInstance(Locale.forLanguageTag("vi-VN")).format(value.decimalValue()) + "đ";
 }
}
