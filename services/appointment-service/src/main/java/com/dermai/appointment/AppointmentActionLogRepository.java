package com.dermai.appointment;

import org.springframework.data.jpa.repository.JpaRepository;
import java.util.List;
import java.util.UUID;

interface AppointmentActionLogRepository extends JpaRepository<AppointmentActionLog,UUID> {
 List<AppointmentActionLog> findTop100ByActorIdentityIdOrderByCreatedAtDesc(UUID actorIdentityId);
}
