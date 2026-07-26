package com.dermai.appointment;
import org.springframework.stereotype.Component;import org.springframework.web.socket.*;import org.springframework.web.socket.handler.*;import java.util.Set;import java.util.concurrent.ConcurrentHashMap;
@Component class SlotWebSocketHandler extends TextWebSocketHandler{
 private final Set<WebSocketSession> sessions=ConcurrentHashMap.newKeySet();
 @Override public void afterConnectionEstablished(WebSocketSession session){sessions.add(new ConcurrentWebSocketSessionDecorator(session,5000,65536));}
 @Override public void afterConnectionClosed(WebSocketSession session,CloseStatus status){sessions.removeIf(x->x.getId().equals(session.getId()));}
 void broadcast(String type){var message=new TextMessage("{\"type\":\""+type+"\"}");sessions.removeIf(session->{try{if(!session.isOpen())return true;session.sendMessage(message);return false;}catch(Exception ignored){return true;}});}
}
