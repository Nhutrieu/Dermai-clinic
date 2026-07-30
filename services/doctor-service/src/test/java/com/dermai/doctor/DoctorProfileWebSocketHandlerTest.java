package com.dermai.doctor;

import static org.mockito.ArgumentMatchers.argThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import java.util.UUID;
import org.springframework.web.socket.WebSocketMessage;
import org.junit.jupiter.api.Test;
import org.springframework.web.socket.WebSocketSession;

class DoctorProfileWebSocketHandlerTest {
  @Test
  void broadcastsProfileUpdateWithDoctorId() throws Exception {
    var session = mock(WebSocketSession.class);
    when(session.getId()).thenReturn("doctor-profile-session");
    when(session.isOpen()).thenReturn(true);
    var handler = new DoctorProfileWebSocketHandler();
    handler.afterConnectionEstablished(session);
    var doctorId = UUID.randomUUID();

    handler.broadcastUpdated(doctorId);

    verify(session).sendMessage(argThat((WebSocketMessage<?> message) ->
        String.valueOf(message.getPayload()).contains("DOCTOR_PROFILE_UPDATED")
            && String.valueOf(message.getPayload()).contains(doctorId.toString())
    ));
  }
}
