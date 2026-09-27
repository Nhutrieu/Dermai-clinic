package com.dermai.patient;

import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;
import java.util.List;
import java.util.UUID;

@RestController
@RequestMapping("/api/v1/patients/audit")
class AiPrivacyController {
  private final AiPrivacyService privacy;

  AiPrivacyController(AiPrivacyService privacy) {
    this.privacy = privacy;
  }

  @GetMapping("/ai-access")
  List<AiPrivacyService.AuditView> recentAiAccess(
      @RequestHeader("X-User-Id") UUID identity,
      @RequestHeader("X-User-Role") String role) {
    if (!"ADMIN".equals(role)) throw new ResponseStatusException(HttpStatus.FORBIDDEN);
    List<AiPrivacyService.AuditView> result = privacy.recent();
    privacy.audit(null, null, identity, role, "VIEWED_AI_AUDIT_LOG");
    return result;
  }
}
