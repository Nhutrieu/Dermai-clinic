package com.dermai.appointment;

import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.*;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.web.server.ResponseStatusException;

class PatientIdentityLinkControllerTest {
 @Test void relinksAppointmentsMessagesAndNotificationsTogether(){
  var appointments=mock(AppointmentRepository.class);var messages=mock(SupportMessageRepository.class);var conversations=mock(SupportConversationRepository.class);var notifications=mock(AppointmentNotificationRepository.class);var updates=mock(SlotUpdateBroadcaster.class);var controller=new PatientIdentityLinkController(appointments,messages,conversations,notifications,updates,"internal-secret");
  var patientId=UUID.randomUUID();var oldIdentity=UUID.randomUUID();var newIdentity=UUID.randomUUID();controller.link("internal-secret",new PatientIdentityLinkController.Link(patientId,oldIdentity,newIdentity));
  verify(appointments).relinkPatientIdentity(patientId,oldIdentity,newIdentity);verify(conversations).mergeIdentity(oldIdentity,newIdentity);verify(conversations).deleteIdentity(oldIdentity);verify(messages).relinkPatient(oldIdentity,newIdentity);verify(messages).relinkSender(oldIdentity,newIdentity);verify(notifications).relinkPatient(oldIdentity,newIdentity);verify(updates).chatChanged();verify(updates).afterCommit();
 }

 @Test void rejectsCallsWithoutTheConfiguredServiceToken(){
  var controller=new PatientIdentityLinkController(mock(AppointmentRepository.class),mock(SupportMessageRepository.class),mock(SupportConversationRepository.class),mock(AppointmentNotificationRepository.class),mock(SlotUpdateBroadcaster.class),"internal-secret");
  assertThatThrownBy(()->controller.link("wrong",new PatientIdentityLinkController.Link(UUID.randomUUID(),UUID.randomUUID(),UUID.randomUUID()))).isInstanceOf(ResponseStatusException.class);
 }
}
