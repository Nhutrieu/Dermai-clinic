package com.dermai.appointment;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import java.util.List;
import java.util.Set;
import java.util.UUID;

@Service
class AppointmentActionAuditService {
 private static final Set<String> STAFF_ROLES=Set.of("RECEPTIONIST","ADMIN");
 private final AppointmentActionLogRepository logs;
 AppointmentActionAuditService(AppointmentActionLogRepository logs){this.logs=logs;}

 @Transactional
 void record(UUID appointmentId,UUID actorIdentityId,String actorRole,String actionType){
  if(STAFF_ROLES.contains(actorRole))logs.save(new AppointmentActionLog(appointmentId,actorIdentityId,actorRole,actionType));
 }

 @Transactional(readOnly=true)
 List<AppointmentActionLog> recentFor(UUID actorIdentityId){return logs.findTop100ByActorIdentityIdOrderByCreatedAtDesc(actorIdentityId);}
}
