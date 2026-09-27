package com.dermai.patient;

import org.springframework.data.jpa.repository.JpaRepository;
import java.util.List;
import java.util.UUID;

interface AiAccessAuditLogRepository extends JpaRepository<AiAccessAuditLog, UUID> {
  List<AiAccessAuditLog> findTop200ByOrderByCreatedAtDesc();
}
