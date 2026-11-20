package com.dermai.appointment;

import static org.assertj.core.api.Assertions.*;
import static org.mockito.Mockito.*;
import java.util.*;
import org.junit.jupiter.api.Test;

class AdminNotificationControllerTest {
 @Test void onlyAdminCanReadOrMarkNotifications() {
  var reads=mock(AdminNotificationReadService.class);var controller=new AdminNotificationController(reads);var identity=UUID.randomUUID();
  for(var role:List.of("PATIENT","DOCTOR","RECEPTIONIST","PHARMACIST")) {
   assertThatThrownBy(()->controller.list(identity,role)).isInstanceOf(AppointmentController.Forbidden.class);
   assertThatThrownBy(()->controller.mark(identity,role,new AdminNotificationController.MarkRead(List.of("leave:1"))))
     .isInstanceOf(AppointmentController.Forbidden.class);
  }
  verifyNoInteractions(reads);
 }
 @Test void readStateAlwaysUsesTheAuthenticatedAdminIdentity() {
  var reads=mock(AdminNotificationReadService.class);var controller=new AdminNotificationController(reads);
  var first=UUID.randomUUID();var second=UUID.randomUUID();
  when(reads.list(first)).thenReturn(List.of("leave:1"));when(reads.list(second)).thenReturn(List.of());
  assertThat(controller.list(first,"ADMIN")).containsExactly("leave:1");
  assertThat(controller.list(second,"ADMIN")).isEmpty();
  controller.mark(second,"ADMIN",new AdminNotificationController.MarkRead(List.of("review:2")));
  verify(reads).mark(second,List.of("review:2"));verify(reads,never()).mark(eq(first),any());
 }
}
