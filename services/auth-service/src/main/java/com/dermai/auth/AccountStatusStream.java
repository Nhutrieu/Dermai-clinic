package com.dermai.auth;

import java.io.IOException;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import org.springframework.stereotype.Component;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

@Component
class AccountStatusStream {
  private final ConcurrentHashMap<UUID, Set<SseEmitter>> subscribers = new ConcurrentHashMap<>();

  SseEmitter subscribe(UUID identityId) {
    var emitter = new SseEmitter(0L);
    subscribers.computeIfAbsent(identityId, ignored -> ConcurrentHashMap.newKeySet()).add(emitter);
    Runnable cleanup = () -> subscribers.computeIfPresent(identityId, (ignored, items) -> {
      items.remove(emitter);
      return items.isEmpty() ? null : items;
    });
    emitter.onCompletion(cleanup);
    emitter.onTimeout(() -> { cleanup.run(); emitter.complete(); });
    try { emitter.send(SseEmitter.event().name("ready").data("ready")); }
    catch (IOException error) { cleanup.run(); emitter.completeWithError(error); }
    return emitter;
  }

  void publish(UUID identityId, String status) {
    var items = subscribers.get(identityId);
    if (items == null) return;
    for (var emitter : items) {
      try { emitter.send(SseEmitter.event().name("account-status").data(new AccountStatusEvent(identityId, status))); }
      catch (IOException error) { emitter.completeWithError(error); }
    }
  }

  record AccountStatusEvent(String type, UUID identityId, String status) {
    AccountStatusEvent(UUID identityId, String status) { this("ACCOUNT_STATUS_CHANGED", identityId, status); }
  }
}