package com.dermai.appointment;
import org.springframework.context.annotation.Configuration;import org.springframework.web.socket.config.annotation.*;
@Configuration @EnableWebSocket class SlotWebSocketConfig implements WebSocketConfigurer{
 private final SlotWebSocketHandler handler;SlotWebSocketConfig(SlotWebSocketHandler handler){this.handler=handler;}
 @Override public void registerWebSocketHandlers(WebSocketHandlerRegistry registry){registry.addHandler(handler,"/api/v1/appointments/ws/slots").setAllowedOriginPatterns("*");}
}
