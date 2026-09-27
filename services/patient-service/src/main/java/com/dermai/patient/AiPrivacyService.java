package com.dermai.patient;

import jakarta.servlet.http.HttpServletRequest;
import org.springframework.stereotype.Service;
import org.springframework.web.context.request.RequestContextHolder;
import org.springframework.web.context.request.ServletRequestAttributes;
import java.time.Instant;
import java.util.List;
import java.util.UUID;

@Service
class AiPrivacyService {
  static final String PURPOSE = "AI_SKIN_IMAGE_ANALYSIS";
  static final String POLICY_VERSION = "ai-skin-analysis-v1";
  private final AiConsentEventRepository consents;
  private final AiAccessAuditLogRepository auditLogs;
  record AuditView(UUID id, UUID assessmentId, UUID patientIdentityId, UUID actorIdentityId,
      String actorRole, String actionType, String sourceIp, String userAgent, Instant createdAt) {}

  AiPrivacyService(AiConsentEventRepository consents, AiAccessAuditLogRepository auditLogs) {
    this.consents = consents;
    this.auditLogs = auditLogs;
  }

  AiConsentEvent grant(UUID patientIdentityId) {
    return consents.save(new AiConsentEvent(patientIdentityId, PURPOSE, POLICY_VERSION));
  }

  void audit(UUID assessmentId, UUID patientIdentityId, UUID actorIdentityId,
      String actorRole, String actionType) {
    HttpServletRequest request = currentRequest();
    String sourceIp = request == null ? null : sourceIp(request);
    String userAgent = request == null ? null : limit(request.getHeader("User-Agent"), 500);
    auditLogs.save(new AiAccessAuditLog(
        assessmentId, patientIdentityId, actorIdentityId, actorRole, actionType, sourceIp, userAgent));
  }

  List<AuditView> recent() {
    return auditLogs.findTop200ByOrderByCreatedAtDesc().stream()
        .map(value -> new AuditView(value.id, value.assessmentId, value.patientIdentityId,
            value.actorIdentityId, value.actorRole, value.actionType, value.sourceIp,
            value.userAgent, value.createdAt))
        .toList();
  }

  private HttpServletRequest currentRequest() {
    var attributes = RequestContextHolder.getRequestAttributes();
    return attributes instanceof ServletRequestAttributes servlet ? servlet.getRequest() : null;
  }

  private String sourceIp(HttpServletRequest request) {
    String forwarded = request.getHeader("X-Forwarded-For");
    if (forwarded == null || forwarded.isBlank()) return limit(request.getRemoteAddr(), 64);
    String[] values = forwarded.split(",");
    return limit(values[values.length - 1].trim(), 64);
  }

  private String limit(String value, int max) {
    if (value == null) return null;
    return value.length() <= max ? value : value.substring(0, max);
  }
}
