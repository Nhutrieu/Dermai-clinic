package com.dermai.appointment;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.time.*;
import java.time.format.DateTimeFormatter;
import java.text.NumberFormat;
import java.util.Locale;
import java.util.UUID;
import org.springframework.amqp.core.*;
import org.springframework.amqp.rabbit.annotation.RabbitListener;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.context.annotation.*;
import org.springframework.stereotype.Component;

@Configuration class PaymentBookingMessaging{
 @Bean TopicExchange bookingEventsExchange(){return ExchangeBuilder.topicExchange("booking_events").durable(true).build();}
 @Bean Queue bookingPaymentQueue(){return QueueBuilder.durable("dermai.booking-payments").build();}
 @Bean Binding paidBinding(@Qualifier("bookingPaymentQueue")Queue queue,@Qualifier("bookingEventsExchange")TopicExchange exchange){return BindingBuilder.bind(queue).to(exchange).with("booking.paid");}
 @Bean Binding expiredBinding(@Qualifier("bookingPaymentQueue")Queue queue,@Qualifier("bookingEventsExchange")TopicExchange exchange){return BindingBuilder.bind(queue).to(exchange).with("booking.payment_expired");}
 @Bean Binding cancelledBinding(@Qualifier("bookingPaymentQueue")Queue queue,@Qualifier("bookingEventsExchange")TopicExchange exchange){return BindingBuilder.bind(queue).to(exchange).with("booking.payment_cancelled");}
 @Bean Binding paymentLinkBinding(@Qualifier("bookingPaymentQueue")Queue queue,@Qualifier("bookingEventsExchange")TopicExchange exchange){return BindingBuilder.bind(queue).to(exchange).with("payment.link_created");}
 @Bean Binding refundedBinding(@Qualifier("bookingPaymentQueue")Queue queue,@Qualifier("bookingEventsExchange")TopicExchange exchange){return BindingBuilder.bind(queue).to(exchange).with("payment.refunded");}
 @Bean Binding refundRequestedBinding(@Qualifier("bookingPaymentQueue")Queue queue,@Qualifier("bookingEventsExchange")TopicExchange exchange){return BindingBuilder.bind(queue).to(exchange).with("payment.refund_requested");}
}
@Component class PaymentBookingConsumer{
 private static final DateTimeFormatter DEADLINE_FORMAT=DateTimeFormatter.ofPattern("HH:mm 'ngày' dd/MM/yyyy").withZone(ZoneId.of("Asia/Ho_Chi_Minh"));
 private final AppointmentService service;private final SupportMessageRepository messages;private final AppointmentNotificationRepository notifications;private final ReceptionNotificationRepository receptionNotifications;private final SlotUpdateBroadcaster updates;private final ObjectMapper json;
 PaymentBookingConsumer(AppointmentService service,SupportMessageRepository messages,AppointmentNotificationRepository notifications,ReceptionNotificationRepository receptionNotifications,SlotUpdateBroadcaster updates,ObjectMapper json){this.service=service;this.messages=messages;this.notifications=notifications;this.receptionNotifications=receptionNotifications;this.updates=updates;this.json=json;}

 @RabbitListener(queues="dermai.booking-payments") public void consume(String payload)throws Exception{
  var event=json.readTree(payload);
  var status=event.path("status").asText();
  if("PAYMENT_PENDING".equals(status)){paymentLinkCreated(event);return;}
  if("REFUNDED".equals(status)){refundCompleted(event);return;}
  if("REFUND_REQUESTED".equals(status)){refundRequested(event);return;}
  var bookingId=UUID.fromString(event.path("bookingId").asText());
  switch(event.path("status").asText()){
   case "CONFIRMED"->paymentConfirmed(event,bookingId);
   case "CANCELLED"->paymentCancelled(event,bookingId);
   default->service.paymentExpired(bookingId);
  }
 }

 private void paymentConfirmed(JsonNode event,UUID bookingId){
  service.paymentConfirmed(bookingId);
  var type="APPOINTMENT_PENDING_CONFIRMATION";
  if(receptionNotifications.existsByAppointmentIdAndNotificationType(bookingId,type))return;
  var patientIdentityValue=event.path("patientIdentityId").asText();
  if(patientIdentityValue.isBlank())return;
  var patientIdentityId=UUID.fromString(patientIdentityValue);
  var startAt=event.path("startAt").asText();
  var appointmentTime=startAt.isBlank()?"lịch vừa đặt":DEADLINE_FORMAT.format(Instant.parse(startAt));
  receptionNotifications.save(new ReceptionNotification(
   bookingId,
   patientIdentityId,
   type,
   "Có lịch mới chờ xác nhận",
   "Bệnh nhân đã thanh toán tiền cọc cho lịch lúc "+appointmentTime+". Vui lòng kiểm tra và xác nhận lịch."
  ));
  updates.receptionNotificationsChanged();
 }

 private void refundRequested(JsonNode event){
  var bookingId=UUID.fromString(event.path("bookingId").asText());
  var type="PAYMENT_REFUND_REQUESTED";if(receptionNotifications.existsByAppointmentIdAndNotificationType(bookingId,type))return;
  var patientIdentityId=UUID.fromString(event.path("patientIdentityId").asText());
  var policyValue=event.hasNonNull("refundAmount")?event.path("refundAmount").decimalValue():event.path("amount").decimalValue();
  var amount=NumberFormat.getIntegerInstance(Locale.forLanguageTag("vi-VN")).format(policyValue)+"đ";
  var clinic="CLINIC".equals(event.path("refundInitiator").asText());
  var title=clinic?"Phòng khám cần hoàn tiền cọc":"Bệnh nhân yêu cầu hoàn tiền cọc";
  var body=clinic?"Lịch đã được phòng khám chủ động hủy. Cần hoàn đủ "+amount+" cho bệnh nhân.":"Bệnh nhân đã hủy lịch và vừa gửi yêu cầu hoàn cọc "+amount+". Vui lòng kiểm tra chính sách trước khi xử lý.";
  receptionNotifications.save(new ReceptionNotification(bookingId,patientIdentityId,type,title,body));
  updates.receptionNotificationsChanged();
 }
 private void refundCompleted(JsonNode event){
  var bookingId=UUID.fromString(event.path("bookingId").asText());
  var type="PAYMENT_REFUNDED";if(notifications.existsByAppointmentIdAndNotificationType(bookingId,type))return;
  var patientIdentityId=UUID.fromString(event.path("patientIdentityId").asText());
  var amount=NumberFormat.getIntegerInstance(Locale.forLanguageTag("vi-VN")).format(event.path("refundAmount").decimalValue())+"đ";
  var cash="CASH".equals(event.path("refundMethod").asText());
  var proof=cash?event.path("refundReceiptNumber").asText():event.path("refundReference").asText();
  var notification=new AppointmentNotification();notification.id=UUID.randomUUID();notification.patientIdentityId=patientIdentityId;notification.appointmentId=bookingId;
  notification.notificationType=type;notification.title="Đã hoàn tiền cọc";
  notification.body="Phòng khám đã hoàn "+amount+" qua "+(cash?"tiền mặt":"chuyển khoản")+(proof.isBlank()?"":". "+(cash?"Số phiếu: ":"Mã giao dịch: ")+proof)+". Vui lòng kiểm tra và liên hệ lễ tân nếu cần hỗ trợ.";
  notification.createdAt=Instant.now();notifications.save(notification);updates.chatChanged();
 }
 private void paymentCancelled(JsonNode event,UUID bookingId){
  service.paymentCancelled(bookingId);
  var type="PAYMENT_CANCELLED_BY_PATIENT";
  if(receptionNotifications.existsByAppointmentIdAndNotificationType(bookingId,type))return;
  var patientIdentityId=UUID.fromString(event.path("patientIdentityId").asText());
  var startAt=event.path("startAt").asText();
  var appointmentTime=startAt.isBlank()?"lịch vừa đặt":DEADLINE_FORMAT.format(Instant.parse(startAt));
  receptionNotifications.save(new ReceptionNotification(bookingId,patientIdentityId,type,"Bệnh nhân đã hủy trước khi thanh toán","Lịch "+appointmentTime+" đã được hủy. Không phát sinh hoàn tiền và khung giờ đã được trả lại."));
  updates.receptionNotificationsChanged();
 }
 private void paymentLinkCreated(JsonNode event){
  var eventId=UUID.fromString(event.path("eventId").asText());
  var bookingId=UUID.fromString(event.path("bookingId").asText());
  var patientIdentityId=UUID.fromString(event.path("patientIdentityId").asText());
  var checkoutUrl=event.path("checkoutUrl").asText();
  var expiresAt=event.path("expiresAt").asText();
  var deadline=DEADLINE_FORMAT.format(Instant.parse(expiresAt));
  var depositAmount=NumberFormat.getIntegerInstance(Locale.forLanguageTag("vi-VN")).format(event.path("amount").asLong())+"đ";
  if(checkoutUrl.isBlank())return;

  if(!notifications.existsByAppointmentIdAndNotificationType(bookingId,"PAYMENT_LINK_CREATED")){
   var notification=new AppointmentNotification();
   notification.id=UUID.randomUUID();notification.patientIdentityId=patientIdentityId;notification.appointmentId=bookingId;
   notification.notificationType="PAYMENT_LINK_CREATED";notification.title="Đã gửi link thanh toán cọc";
   notification.body="Kiểm tra email hoặc mở Hỗ trợ để thanh toán cọc "+depositAmount+" trong 10 phút.";
   notification.createdAt=Instant.now();notifications.save(notification);
  }

  if(!messages.existsById(eventId)){
   var message=new SupportMessage();message.id=eventId;message.patientIdentityId=patientIdentityId;message.senderIdentityId=eventId;message.senderRole="SYSTEM";
   message.body="Phòng khám đã tạo lịch và gửi link thanh toán cọc "+depositAmount+". Hạn thanh toán: "+deadline+"\n"+checkoutUrl;
   message.sentAt=Instant.now();messages.save(message);
  }
  updates.chatChanged();
 }
}
