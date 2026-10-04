package com.dermai.appointment;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.*;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;

class BillingReceptionNotificationConsumerTest {
 @Test
 void invoiceCreatedEventCreatesOneUnreadReceptionNotification() throws Exception {
  var notifications = mock(ReceptionNotificationRepository.class);
  var updates = mock(SlotUpdateBroadcaster.class);
  var consumer = new BillingReceptionNotificationConsumer(notifications, updates, new ObjectMapper());
  var appointmentId = UUID.randomUUID();
  var patientIdentityId = UUID.randomUUID();
  var invoiceId = UUID.randomUUID();
  when(notifications.existsByAppointmentIdAndNotificationType(appointmentId, "INVOICE_CREATED")).thenReturn(false, true);
  var payload = """
    {"invoiceId":"%s","appointmentId":"%s","patientIdentityId":"%s","status":"CREATED","totalAmount":350000,"remainingAmount":250000}
    """.formatted(invoiceId, appointmentId, patientIdentityId);

  consumer.consume(payload);
  consumer.consume(payload);

  var saved = ArgumentCaptor.forClass(ReceptionNotification.class);
  verify(notifications).save(saved.capture());
  assertThat(saved.getValue().appointmentId).isEqualTo(appointmentId);
  assertThat(saved.getValue().patientIdentityId).isEqualTo(patientIdentityId);
  assertThat(saved.getValue().notificationType).isEqualTo("INVOICE_CREATED");
  assertThat(saved.getValue().title).isEqualTo("Có hóa đơn mới");
  assertThat(saved.getValue().body).contains("350.000đ").contains("250.000đ").contains(invoiceId.toString().substring(0, 8).toUpperCase());
  assertThat(saved.getValue().readAt).isNull();
  verify(updates).receptionNotificationsChanged();
 }

 @Test
 void invoicePaidEventCreatesPaidReceptionNotification() throws Exception {
  var notifications = mock(ReceptionNotificationRepository.class);
  var updates = mock(SlotUpdateBroadcaster.class);
  var consumer = new BillingReceptionNotificationConsumer(notifications, updates, new ObjectMapper());
  var appointmentId = UUID.randomUUID();
  var patientIdentityId = UUID.randomUUID();
  var invoiceId = UUID.randomUUID();
  var payload = """
    {"invoiceId":"%s","appointmentId":"%s","patientIdentityId":"%s","status":"PAID","totalAmount":350000,"remainingAmount":0}
    """.formatted(invoiceId, appointmentId, patientIdentityId);

  consumer.consume(payload);

  var saved = ArgumentCaptor.forClass(ReceptionNotification.class);
  verify(notifications).save(saved.capture());
  assertThat(saved.getValue().notificationType).isEqualTo("INVOICE_PAID");
  assertThat(saved.getValue().title).isEqualTo("Hóa đơn đã thanh toán");
  assertThat(saved.getValue().body).contains("350.000đ").contains("bước tiếp theo");
  verify(updates).receptionNotificationsChanged();
 }
}
