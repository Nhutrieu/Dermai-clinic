package com.dermai.payment;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.UUID;
import org.springframework.amqp.core.*;
import org.springframework.amqp.rabbit.annotation.RabbitListener;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.context.annotation.*;
import org.springframework.stereotype.Component;

@Configuration
class AppointmentCancellationMessaging {
 @Bean TopicExchange appointmentEventsExchange(){return ExchangeBuilder.topicExchange("dermai.appointments").durable(true).build();}
 @Bean Queue paymentAppointmentCancellationQueue(){return QueueBuilder.durable("dermai.payments.appointment-cancellations").build();}
 @Bean Binding appointmentCancelledPaymentBinding(@Qualifier("paymentAppointmentCancellationQueue")Queue queue,@Qualifier("appointmentEventsExchange")TopicExchange exchange){return BindingBuilder.bind(queue).to(exchange).with("AppointmentCancelled");}
}

@Component
class AppointmentCancellationConsumer {
 private final PaymentService payments;
 private final ObjectMapper json;
 AppointmentCancellationConsumer(PaymentService payments,ObjectMapper json){this.payments=payments;this.json=json;}

 @RabbitListener(queues="dermai.payments.appointment-cancellations")
 void consume(String payload)throws Exception{
  var event=json.readTree(payload);
  var bookingId=UUID.fromString(event.path("appointmentId").asText());
  var actorValue=event.path("actorIdentityId").asText("");
  var actorIdentityId=actorValue.isBlank()?null:UUID.fromString(actorValue);
  var initiator=event.path("cancellationInitiator").asText("PATIENT_REQUEST");
  if("CLINIC".equals(initiator))payments.requestRefund(bookingId,actorIdentityId,event.path("actorRole").asText("SYSTEM"),initiator,event.path("cancelReason").asText("Phòng khám hủy lịch"));
 }
}