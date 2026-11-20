package com.dermai.appointment;

import jakarta.validation.Valid;
import jakarta.validation.constraints.*;
import java.util.List;
import java.util.UUID;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/v1/appointments/admin-notifications/read")
class AdminNotificationController {
 private final AdminNotificationReadService reads;
 AdminNotificationController(AdminNotificationReadService reads){this.reads=reads;}
 record MarkRead(@NotNull @Size(max=1000) List<@NotBlank @Size(max=240) String> keys) {}
 @GetMapping List<String> list(@RequestHeader("X-User-Id") UUID identity,@RequestHeader("X-User-Role") String role) {
  requireAdmin(role);return reads.list(identity);
 }
 @PutMapping ResponseEntity<Void> mark(@RequestHeader("X-User-Id") UUID identity,@RequestHeader("X-User-Role") String role,@Valid @RequestBody MarkRead body) {
  requireAdmin(role);reads.mark(identity,body.keys());return ResponseEntity.noContent().build();
 }
 private void requireAdmin(String role){if(!"ADMIN".equals(role))throw new AppointmentController.Forbidden();}
}
