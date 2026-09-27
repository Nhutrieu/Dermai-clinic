package com.dermai.appointment;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class PaymentBookingConsumerTest {
 @Test
 void paymentLinkEventCreatesOneInAppNotificationAndOneSystemChatMessage() throws Exception {
  var service=mock(AppointmentService.class);
  var messages=mock(SupportMessageRepository.class);
  var notifications=mock(AppointmentNotificationRepository.class);
  var updates=mock(SlotUpdateBroadcaster.class);
  var consumer=new PaymentBookingConsumer(service,messages,notifications,mock(ReceptionNotificationRepository.class),updates,new ObjectMapper());
  var eventId=UUID.randomUUID();
  var bookingId=UUID.randomUUID();
  var patientIdentityId=UUID.randomUUID();
  when(notifications.existsByAppointmentIdAndNotificationType(bookingId,"PAYMENT_LINK_CREATED")).thenReturn(false,true);
  when(messages.existsById(eventId)).thenReturn(false,true);
  var payload="{\"eventId\":\""+eventId+"\",\"bookingId\":\""+bookingId+"\",\"patientIdentityId\":\""+patientIdentityId+"\",\"status\":\"PAYMENT_PENDING\",\"amount\":2000,\"checkoutUrl\":\"https://checkout.example/pay\",\"expiresAt\":\"2026-09-22T14:10:00Z\"}";

  consumer.consume(payload);
  consumer.consume(payload);

  var notification=org.mockito.ArgumentCaptor.forClass(AppointmentNotification.class);
  verify(notifications).save(notification.capture());
  assertThat(notification.getValue().patientIdentityId).isEqualTo(patientIdentityId);
  assertThat(notification.getValue().notificationType).isEqualTo("PAYMENT_LINK_CREATED");

  var message=org.mockito.ArgumentCaptor.forClass(SupportMessage.class);
  verify(messages).save(message.capture());
  assertThat(message.getValue().senderRole).isEqualTo("SYSTEM");
  assertThat(message.getValue().body).contains("2.000đ").contains("https://checkout.example/pay");
  verifyNoInteractions(service);
  verify(updates,times(2)).chatChanged();
 }

 @Test
 void cancelledPaymentCreatesUnreadReceptionNotification() throws Exception {
  var service=mock(AppointmentService.class);
  var receptionNotifications=mock(ReceptionNotificationRepository.class);
  var updates=mock(SlotUpdateBroadcaster.class);
  var consumer=new PaymentBookingConsumer(service,mock(SupportMessageRepository.class),mock(AppointmentNotificationRepository.class),receptionNotifications,updates,new ObjectMapper());
  var bookingId=UUID.randomUUID();
  var patientIdentityId=UUID.randomUUID();
  when(receptionNotifications.existsByAppointmentIdAndNotificationType(bookingId,"PAYMENT_CANCELLED_BY_PATIENT")).thenReturn(false,true);

  consumer.consume("{\"bookingId\":\""+bookingId+"\",\"patientIdentityId\":\""+patientIdentityId+"\",\"status\":\"CANCELLED\",\"startAt\":\"2026-09-23T00:00:00Z\"}");
  consumer.consume("{\"bookingId\":\""+bookingId+"\",\"patientIdentityId\":\""+patientIdentityId+"\",\"status\":\"CANCELLED\",\"startAt\":\"2026-09-23T00:00:00Z\"}");

  verify(service,times(2)).paymentCancelled(bookingId);
  var notification=org.mockito.ArgumentCaptor.forClass(ReceptionNotification.class);
  verify(receptionNotifications).save(notification.capture());
  assertThat(notification.getValue().patientIdentityId).isEqualTo(patientIdentityId);
  assertThat(notification.getValue().notificationType).isEqualTo("PAYMENT_CANCELLED_BY_PATIENT");
  assertThat(notification.getValue().readAt).isNull();
  verify(updates).receptionNotificationsChanged();
 }
 @Test
 void refundRequestCreatesOneReceptionNotification() throws Exception {
  var receptionNotifications=mock(ReceptionNotificationRepository.class);var updates=mock(SlotUpdateBroadcaster.class);
  var consumer=new PaymentBookingConsumer(mock(AppointmentService.class),mock(SupportMessageRepository.class),mock(AppointmentNotificationRepository.class),receptionNotifications,updates,new ObjectMapper());
  var bookingId=UUID.randomUUID();var patientIdentityId=UUID.randomUUID();
  when(receptionNotifications.existsByAppointmentIdAndNotificationType(bookingId,"PAYMENT_REFUND_REQUESTED")).thenReturn(false,true);
  var payload="{\"bookingId\":\""+bookingId+"\",\"patientIdentityId\":\""+patientIdentityId+"\",\"status\":\"REFUND_REQUESTED\",\"amount\":2000,\"refundAmount\":1000,\"refundInitiator\":\"PATIENT_REQUEST\"}";

  consumer.consume(payload);consumer.consume(payload);

  var notification=org.mockito.ArgumentCaptor.forClass(ReceptionNotification.class);verify(receptionNotifications).save(notification.capture());
  assertThat(notification.getValue().notificationType).isEqualTo("PAYMENT_REFUND_REQUESTED");
  assertThat(notification.getValue().title).contains("yêu cầu hoàn tiền cọc");
  assertThat(notification.getValue().body).contains("1.000đ").contains("kiểm tra chính sách");
  verify(updates).receptionNotificationsChanged();
 }
 @Test
 void refundedEventCreatesPatientNotificationWithoutExpiringAppointment() throws Exception {
  var service=mock(AppointmentService.class);
  var notifications=mock(AppointmentNotificationRepository.class);
  var updates=mock(SlotUpdateBroadcaster.class);
  var consumer=new PaymentBookingConsumer(service,mock(SupportMessageRepository.class),notifications,mock(ReceptionNotificationRepository.class),updates,new ObjectMapper());
  var bookingId=UUID.randomUUID();var patientIdentityId=UUID.randomUUID();
  when(notifications.existsByAppointmentIdAndNotificationType(bookingId,"PAYMENT_REFUNDED")).thenReturn(false);

  consumer.consume("{\"bookingId\":\""+bookingId+"\",\"patientIdentityId\":\""+patientIdentityId+"\",\"status\":\"REFUNDED\",\"refundAmount\":2000,\"refundMethod\":\"BANK_TRANSFER\",\"refundReference\":\"RF-001\"}");

  var notification=org.mockito.ArgumentCaptor.forClass(AppointmentNotification.class);verify(notifications).save(notification.capture());
  assertThat(notification.getValue().patientIdentityId).isEqualTo(patientIdentityId);
  assertThat(notification.getValue().notificationType).isEqualTo("PAYMENT_REFUNDED");
  assertThat(notification.getValue().title).isEqualTo("Đã hoàn tiền cọc");
  assertThat(notification.getValue().body).contains("2.000đ").contains("chuyển khoản").contains("RF-001");
  verifyNoInteractions(service);
  verify(updates).chatChanged();
 }
 @Test
 void paidEventStillConfirmsTheAppointment() throws Exception {
  var service=mock(AppointmentService.class);
  var consumer=new PaymentBookingConsumer(service,mock(SupportMessageRepository.class),mock(AppointmentNotificationRepository.class),mock(ReceptionNotificationRepository.class),mock(SlotUpdateBroadcaster.class),new ObjectMapper());
  var bookingId=UUID.randomUUID();

  consumer.consume("{\"bookingId\":\""+bookingId+"\",\"status\":\"CONFIRMED\"}");

  verify(service).paymentConfirmed(bookingId);
 }

 @Test
 void paidEventCreatesUnreadReceptionNotification() throws Exception {
  var service=mock(AppointmentService.class);
  var receptionNotifications=mock(ReceptionNotificationRepository.class);
  var updates=mock(SlotUpdateBroadcaster.class);
  var consumer=new PaymentBookingConsumer(service,mock(SupportMessageRepository.class),mock(AppointmentNotificationRepository.class),receptionNotifications,updates,new ObjectMapper());
  var bookingId=UUID.randomUUID();
  var patientIdentityId=UUID.randomUUID();
  when(receptionNotifications.existsByAppointmentIdAndNotificationType(bookingId,"APPOINTMENT_PENDING_CONFIRMATION")).thenReturn(false);
  var payload="""
   {"bookingId":"%s","patientIdentityId":"%s","startAt":"2026-09-27T02:00:00Z","status":"CONFIRMED"}
   """.formatted(bookingId,patientIdentityId);

  consumer.consume(payload);

  verify(service).paymentConfirmed(bookingId);
  var notification=org.mockito.ArgumentCaptor.forClass(ReceptionNotification.class);
  verify(receptionNotifications).save(notification.capture());
  assertThat(notification.getValue().appointmentId).isEqualTo(bookingId);
  assertThat(notification.getValue().patientIdentityId).isEqualTo(patientIdentityId);
  assertThat(notification.getValue().notificationType).isEqualTo("APPOINTMENT_PENDING_CONFIRMATION");
  assertThat(notification.getValue().title).contains("lịch mới").contains("xác nhận");
  assertThat(notification.getValue().body).contains("thanh toán tiền cọc").contains("27/09/2026");
  assertThat(notification.getValue().readAt).isNull();
  verify(updates).receptionNotificationsChanged();
 }
}
