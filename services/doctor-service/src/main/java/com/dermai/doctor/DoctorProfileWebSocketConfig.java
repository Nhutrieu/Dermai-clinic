package com.dermai.doctor;

import org.springframework.context.annotation.Configuration;
import org.springframework.web.socket.config.annotation.EnableWebSocket;
import org.springframework.web.socket.config.annotation.WebSocketConfigurer;
import org.springframework.web.socket.config.annotation.WebSocketHandlerRegistry;

@Configuration
@EnableWebSocket
class DoctorProfileWebSocketConfig implements WebSocketConfigurer {
  private final DoctorProfileWebSocketHandler handler;

  DoctorProfileWebSocketConfig(DoctorProfileWebSocketHandler handler) {
    this.handler = handler;
  }

  @Override
  public void registerWebSocketHandlers(WebSocketHandlerRegistry registry) {
    registry.addHandler(handler, "/api/v1/doctors/ws/profile").setAllowedOriginPatterns("*");
  }
}
