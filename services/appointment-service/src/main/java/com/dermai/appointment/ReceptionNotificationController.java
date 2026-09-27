package com.dermai.appointment;

import java.time.Instant;
import java.util.*;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/v1/appointments/reception-notifications")
class ReceptionNotificationController {
 private final ReceptionNotificationRepository notifications;

 ReceptionNotificationController(ReceptionNotificationRepository notifications) {
  this.notifications = notifications;
 }

 @GetMapping
 List<ReceptionNotification> list(@RequestHeader("X-User-Role") String role) {
  requireStaff(role);
  return notifications.findTop50ByOrderByCreatedAtDesc();
 }

 @PatchMapping("/{id}/read")
 ResponseEntity<Void> read(@PathVariable UUID id, @RequestHeader("X-User-Role") String role) {
  requireStaff(role);
  var notification = notifications.findById(id).orElseThrow(NoSuchElementException::new);
  if (notification.readAt == null) {
   notification.readAt = Instant.now();
   notifications.save(notification);
  }
  return ResponseEntity.noContent().build();
 }

 private void requireStaff(String role) {
  if (!Set.of("RECEPTIONIST", "ADMIN").contains(role)) throw new AppointmentController.Forbidden();
 }
}