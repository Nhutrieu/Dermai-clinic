package com.dermai.patient;

import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;
import java.util.List;
import java.util.UUID;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

class AiPrivacyControllerTest {
  @Test
  void onlyAdminCanReadTheAuditLog() {
    AiPrivacyService privacy = mock(AiPrivacyService.class);
    AiPrivacyController controller = new AiPrivacyController(privacy);
    UUID actor = UUID.randomUUID();
    when(privacy.recent()).thenReturn(List.of());

    assertEquals(0, controller.recentAiAccess(actor, "ADMIN").size());
    verify(privacy).audit(null, null, actor, "ADMIN", "VIEWED_AI_AUDIT_LOG");

    ResponseStatusException error = assertThrows(
        ResponseStatusException.class,
        () -> controller.recentAiAccess(actor, "RECEPTIONIST"));
    assertEquals(HttpStatus.FORBIDDEN, error.getStatusCode());
  }
}
