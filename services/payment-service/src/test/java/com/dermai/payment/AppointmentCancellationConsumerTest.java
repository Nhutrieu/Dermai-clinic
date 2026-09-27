package com.dermai.payment;

import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class AppointmentCancellationConsumerTest {
 @Test void patientCancellationDoesNotAutomaticallyRequestRefund() throws Exception {
  var payments=mock(PaymentService.class);var consumer=new AppointmentCancellationConsumer(payments,new ObjectMapper());
  consumer.consume("{\"appointmentId\":\""+UUID.randomUUID()+"\",\"actorIdentityId\":\""+UUID.randomUUID()+"\",\"actorRole\":\"PATIENT\",\"cancellationInitiator\":\"PATIENT_REQUEST\",\"cancelReason\":\"Không còn nhu cầu\"}");
  verifyNoInteractions(payments);
 }
 @Test void clinicCancellationStillRequestsMandatoryRefund() throws Exception {
  var payments=mock(PaymentService.class);var consumer=new AppointmentCancellationConsumer(payments,new ObjectMapper());var bookingId=UUID.randomUUID();var actorId=UUID.randomUUID();
  consumer.consume("{\"appointmentId\":\""+bookingId+"\",\"actorIdentityId\":\""+actorId+"\",\"actorRole\":\"RECEPTIONIST\",\"cancellationInitiator\":\"CLINIC\",\"cancelReason\":\"Bác sĩ nghỉ\"}");
  verify(payments).requestRefund(bookingId,actorId,"RECEPTIONIST","CLINIC","Bác sĩ nghỉ");
 }
}