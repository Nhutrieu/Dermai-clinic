package com.dermai.appointment;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

import java.util.Optional;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;
import org.springframework.mock.web.MockMultipartFile;

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

 @Test void patientCanSendAValidatedPrivatePng()throws Exception{
  var messages=mock(SupportMessageRepository.class);var updates=mock(SlotUpdateBroadcaster.class);var conversations=mock(SupportConversationService.class);
  var controller=new SupportController(messages,updates,conversations);var patient=UUID.randomUUID();
  when(messages.save(any(SupportMessage.class))).thenAnswer(call->call.getArgument(0));
  var png=new byte[]{(byte)0x89,0x50,0x4e,0x47,0x0d,0x0a,0x1a,0x0a,1,2,3};

  var response=controller.sendImage(patient,"PATIENT",null,"QR nhận hoàn tiền",new MockMultipartFile("file","qr.png","image/png",png));

  assertThat(response.getStatusCode()).isEqualTo(HttpStatus.CREATED);
  assertThat(response.getBody().attachmentContentType).isEqualTo("image/png");
  assertThat(response.getBody().attachmentSizeBytes).isEqualTo(png.length);
  assertThat(response.getBody().attachmentData).containsExactly(png);
  verify(conversations).manualEscalate(patient);verify(updates).chatChanged();
 }

 @Test void imageLargerThanFiveMegabytesIsRejected(){
  var controller=new SupportController(mock(SupportMessageRepository.class),mock(SlotUpdateBroadcaster.class),mock(SupportConversationService.class));
  var oversized=new MockMultipartFile("file","large.png","image/png",new byte[5*1024*1024+1]);

  assertThatThrownBy(()->controller.sendImage(UUID.randomUUID(),"PATIENT",null,null,oversized))
   .isInstanceOfSatisfying(ResponseStatusException.class,error->assertThat(error.getStatusCode()).isEqualTo(HttpStatus.PAYLOAD_TOO_LARGE));
 }

 @Test void attachmentIsVisibleOnlyToPatientOrAssignedReceptionist(){
  var messages=mock(SupportMessageRepository.class);var conversations=mock(SupportConversationService.class);
  var controller=new SupportController(messages,mock(SlotUpdateBroadcaster.class),conversations);
  var patient=UUID.randomUUID();var receptionist=UUID.randomUUID();var attachment=new SupportMessage();attachment.id=UUID.randomUUID();attachment.patientIdentityId=patient;attachment.attachmentContentType="image/png";attachment.attachmentOriginalName="qr.png";attachment.attachmentData=new byte[]{1,2,3};
  when(messages.findById(attachment.id)).thenReturn(Optional.of(attachment));

  assertThat(controller.attachment(attachment.id,patient,"PATIENT").getBody()).containsExactly(1,2,3);
  assertThatThrownBy(()->controller.attachment(attachment.id,receptionist,"RECEPTIONIST"))
   .isInstanceOfSatisfying(ResponseStatusException.class,error->assertThat(error.getStatusCode()).isEqualTo(HttpStatus.NOT_FOUND));
  when(conversations.assignedTo(patient,receptionist)).thenReturn(true);
  assertThat(controller.attachment(attachment.id,receptionist,"RECEPTIONIST").getBody()).containsExactly(1,2,3);
  assertThatThrownBy(()->controller.attachment(attachment.id,UUID.randomUUID(),"ADMIN"))
   .isInstanceOfSatisfying(ResponseStatusException.class,error->assertThat(error.getStatusCode()).isEqualTo(HttpStatus.NOT_FOUND));
 }
 @Test void adminCannotListPrivateChatOrConversations(){
  var controller=new SupportController(mock(SupportMessageRepository.class),mock(SlotUpdateBroadcaster.class),mock(SupportConversationService.class));
  var admin=UUID.randomUUID();
  assertThatThrownBy(()->controller.list(admin,"ADMIN",null))
   .isInstanceOfSatisfying(ResponseStatusException.class,error->assertThat(error.getStatusCode()).isEqualTo(HttpStatus.FORBIDDEN));
  assertThatThrownBy(()->controller.conversationList(admin,"ADMIN"))
   .isInstanceOfSatisfying(ResponseStatusException.class,error->assertThat(error.getStatusCode()).isEqualTo(HttpStatus.FORBIDDEN));
 }
 @Test void unassignedReceptionistCannotReadPrivateMessages(){
  var messages=mock(SupportMessageRepository.class);var conversations=mock(SupportConversationService.class);
  var controller=new SupportController(messages,mock(SlotUpdateBroadcaster.class),conversations);
  var patient=UUID.randomUUID();var receptionist=UUID.randomUUID();
  when(conversations.assignedTo(patient,receptionist)).thenReturn(false);

  assertThatThrownBy(()->controller.list(receptionist,"RECEPTIONIST",patient))
   .isInstanceOfSatisfying(ResponseStatusException.class,error->assertThat(error.getStatusCode()).isEqualTo(HttpStatus.NOT_FOUND));
  verify(messages,never()).findByPatientIdentityIdOrderBySentAtAsc(patient);
 }}
