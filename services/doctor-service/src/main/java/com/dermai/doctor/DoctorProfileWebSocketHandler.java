package com.dermai.doctor;

import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import org.springframework.stereotype.Component;
import org.springframework.web.socket.CloseStatus;
import org.springframework.web.socket.TextMessage;
import org.springframework.web.socket.WebSocketSession;
import org.springframework.web.socket.handler.ConcurrentWebSocketSessionDecorator;
import org.springframework.web.socket.handler.TextWebSocketHandler;

@Component
class DoctorProfileWebSocketHandler extends TextWebSocketHandler {
  private final Set<WebSocketSession> sessions = ConcurrentHashMap.newKeySet();

  @Override
  public void afterConnectionEstablished(WebSocketSession session) {
    sessions.add(new ConcurrentWebSocketSessionDecorator(session, 5_000, 65_536));
  }

  @Override
  public void afterConnectionClosed(WebSocketSession session, CloseStatus status) {
    sessions.removeIf(existing -> existing.getId().equals(session.getId()));
  }

  void broadcastUpdated(UUID doctorId) {
    var message = new TextMessage(
        "{\"type\":\"DOCTOR_PROFILE_UPDATED\",\"doctorId\":\"" + doctorId + "\"}"
    );
    sessions.removeIf(session -> {
      try {
        if (!session.isOpen()) return true;
        session.sendMessage(message);
        return false;
      } catch (Exception ignored) {
        return true;
      }
    });
  }
}
