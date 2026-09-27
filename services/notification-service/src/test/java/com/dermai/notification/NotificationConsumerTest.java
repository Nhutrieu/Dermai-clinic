package com.dermai.notification;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.mail.SimpleMailMessage;
import org.springframework.mail.javamail.JavaMailSender;

class NotificationConsumerTest {
 @Test void refundedEventEmailsAmountMethodAndReferenceToPatient() throws Exception {
  var deliveries=mock(DeliveryRepository.class);var mail=mock(JavaMailSender.class);
  when(deliveries.findByEventId(any())).thenReturn(Optional.empty());
  when(deliveries.save(any(Delivery.class))).thenAnswer(call->call.getArgument(0));
  var consumer=new NotificationConsumer(deliveries,mail,new ObjectMapper(),"http://auth-service:8081","service-token","clinic@example.com");
  var eventId=UUID.randomUUID();

  consumer.consume("{\"eventId\":\""+eventId+"\",\"patientIdentityId\":\""+UUID.randomUUID()+"\",\"recipientEmail\":\"patient@example.com\",\"status\":\"REFUNDED\",\"refundAmount\":2000,\"refundMethod\":\"BANK_TRANSFER\",\"refundReference\":\"RF-001\"}");

  var message=ArgumentCaptor.forClass(SimpleMailMessage.class);verify(mail).send(message.capture());
  assertThat(message.getValue().getTo()).containsExactly("patient@example.com");
  assertThat(message.getValue().getSubject()).isEqualTo("DermAI Clinic đã hoàn tiền cọc");
  assertThat(message.getValue().getText()).contains("2.000đ").contains("Chuyển khoản").contains("RF-001");
 }
}