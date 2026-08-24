package com.dermai.appointment;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;

class SupportControllerTest {
 @Test void receptionistMustClaimBeforeReplying(){
  var conversations=mock(SupportConversationService.class);
  var controller=new SupportController(mock(SupportMessageRepository.class),mock(SlotUpdateBroadcaster.class),conversations);
  var patient=UUID.randomUUID();var receptionist=UUID.randomUUID();
  when(conversations.assignedTo(patient,receptionist)).thenReturn(false);

  assertThatThrownBy(()->controller.send(receptionist,"RECEPTIONIST",new SupportController.Send(patient,"Xin chào")))
   .isInstanceOfSatisfying(ResponseStatusException.class,error->assertThat(error.getStatusCode()).isEqualTo(HttpStatus.CONFLICT));
 }

 @Test void assignedReceptionistCanReplyAndConversationIsUpdated(){
  var messages=mock(SupportMessageRepository.class);var updates=mock(SlotUpdateBroadcaster.class);var conversations=mock(SupportConversationService.class);
  var controller=new SupportController(messages,updates,conversations);
  var patient=UUID.randomUUID();var receptionist=UUID.randomUUID();
  when(conversations.assignedTo(patient,receptionist)).thenReturn(true);
  when(messages.save(any(SupportMessage.class))).thenAnswer(call->call.getArgument(0));

  var response=controller.send(receptionist,"RECEPTIONIST",new SupportController.Send(patient,"  Xin chào  "));

  assertThat(response.getBody().body).isEqualTo("Xin chào");
  verify(conversations).touch(patient);verify(updates).chatChanged();
 }

 @Test void adminCanMonitorButCannotSendMessages(){
  var controller=new SupportController(mock(SupportMessageRepository.class),mock(SlotUpdateBroadcaster.class),mock(SupportConversationService.class));
  assertThatThrownBy(()->controller.send(UUID.randomUUID(),"ADMIN",new SupportController.Send(UUID.randomUUID(),"Can thiệp")))
    .isInstanceOfSatisfying(ResponseStatusException.class,error->assertThat(error.getStatusCode()).isEqualTo(HttpStatus.FORBIDDEN));
  }

 @Test void resolvingConversationUsesPatientFacingAssistantName(){
  var messages=mock(SupportMessageRepository.class);var updates=mock(SlotUpdateBroadcaster.class);var conversations=mock(SupportConversationService.class);
  var controller=new SupportController(messages,updates,conversations);
  var patient=UUID.randomUUID();var receptionist=UUID.randomUUID();
  when(messages.save(any(SupportMessage.class))).thenAnswer(call->call.getArgument(0));

  controller.resolve(patient,receptionist,"RECEPTIONIST");

  var saved=org.mockito.ArgumentCaptor.forClass(SupportMessage.class);
  verify(messages).save(saved.capture());
  assertThat(saved.getValue().body).contains("Trợ lý Derm").doesNotContain("Trợ lý DermAI").doesNotContain("AI Assistant");
 }
}
