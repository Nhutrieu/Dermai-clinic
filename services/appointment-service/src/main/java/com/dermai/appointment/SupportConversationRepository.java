package com.dermai.appointment;

import org.springframework.data.jpa.repository.*;
import org.springframework.data.repository.query.Param;
import java.util.*;

interface SupportConversationRepository extends JpaRepository<SupportConversation,UUID> {
 List<SupportConversation> findAllByOrderByUpdatedAtDesc();
 List<SupportConversation> findByChannelStatusNotOrderByUpdatedAtDesc(String channelStatus);
 @Query("select c from SupportConversation c where c.channelStatus<>'AI_ACTIVE' or c.resolvedByIdentityId=:receptionist order by c.updatedAt desc")
 List<SupportConversation> findInboxForReceptionist(@Param("receptionist") UUID receptionistIdentityId);

 @Modifying
 @Query(value="""
  INSERT INTO support_conversations(patient_identity_id,assigned_receptionist_identity_id,assigned_at,channel_status,updated_at)
  VALUES (:patient,:receptionist,now(),'ASSIGNED',now())
  ON CONFLICT (patient_identity_id) DO UPDATE
  SET assigned_receptionist_identity_id=EXCLUDED.assigned_receptionist_identity_id,
      assigned_at=now(),channel_status='ASSIGNED',updated_at=now()
  WHERE support_conversations.channel_status<>'AI_ACTIVE'
    AND (support_conversations.assigned_receptionist_identity_id IS NULL
      OR support_conversations.assigned_receptionist_identity_id=EXCLUDED.assigned_receptionist_identity_id)
  """,nativeQuery=true)
 int claim(@Param("patient") UUID patientIdentityId,@Param("receptionist") UUID receptionistIdentityId);

 @Modifying
 @Query("update SupportConversation c set c.assignedReceptionistIdentityId=null,c.assignedAt=null,c.channelStatus='WAITING_RECEPTIONIST',c.updatedAt=CURRENT_TIMESTAMP where c.patientIdentityId=:patient and c.assignedReceptionistIdentityId=:receptionist")
 int release(@Param("patient") UUID patientIdentityId,@Param("receptionist") UUID receptionistIdentityId);

 @Modifying
 @Query("""
  update SupportConversation c
  set c.assignedReceptionistIdentityId=null,
      c.assignedAt=null,
      c.channelStatus='AI_ACTIVE',
      c.aiFailureCount=0,
      c.lastIntent=null,
      c.lastIntentConfidence=null,
      c.aiSummary=null,
      c.escalationReason=null,
      c.escalatedAt=null,
      c.resolvedAt=CURRENT_TIMESTAMP,
      c.resolvedByIdentityId=:receptionist,
      c.updatedAt=CURRENT_TIMESTAMP
  where c.patientIdentityId=:patient
    and c.channelStatus='ASSIGNED'
    and c.assignedReceptionistIdentityId=:receptionist
  """)
 int resolve(@Param("patient") UUID patientIdentityId,@Param("receptionist") UUID receptionistIdentityId);

 @Modifying
 @Query(value="""
  INSERT INTO support_conversations(patient_identity_id,updated_at)
  VALUES (:patient,now())
  ON CONFLICT (patient_identity_id) DO UPDATE SET updated_at=now()
  """,nativeQuery=true)
 void touch(@Param("patient") UUID patientIdentityId);

 @Modifying
 @Query(value="""
  INSERT INTO support_conversations(patient_identity_id,assigned_receptionist_identity_id,assigned_at,channel_status,ai_failure_count,last_intent,last_intent_confidence,ai_summary,escalation_reason,escalated_at,resolved_at,resolved_by_identity_id,updated_at)
  SELECT :newIdentity,assigned_receptionist_identity_id,assigned_at,channel_status,ai_failure_count,last_intent,last_intent_confidence,ai_summary,escalation_reason,escalated_at,resolved_at,resolved_by_identity_id,updated_at
  FROM support_conversations WHERE patient_identity_id=:oldIdentity
  ON CONFLICT (patient_identity_id) DO UPDATE
  SET assigned_receptionist_identity_id=COALESCE(support_conversations.assigned_receptionist_identity_id,EXCLUDED.assigned_receptionist_identity_id),
      assigned_at=COALESCE(support_conversations.assigned_at,EXCLUDED.assigned_at),
      channel_status=EXCLUDED.channel_status,
      ai_failure_count=GREATEST(support_conversations.ai_failure_count,EXCLUDED.ai_failure_count),
      last_intent=COALESCE(EXCLUDED.last_intent,support_conversations.last_intent),
      last_intent_confidence=COALESCE(EXCLUDED.last_intent_confidence,support_conversations.last_intent_confidence),
      ai_summary=COALESCE(EXCLUDED.ai_summary,support_conversations.ai_summary),
      escalation_reason=COALESCE(EXCLUDED.escalation_reason,support_conversations.escalation_reason),
      escalated_at=COALESCE(support_conversations.escalated_at,EXCLUDED.escalated_at),
      resolved_at=COALESCE(support_conversations.resolved_at,EXCLUDED.resolved_at),
      resolved_by_identity_id=COALESCE(support_conversations.resolved_by_identity_id,EXCLUDED.resolved_by_identity_id),
      updated_at=GREATEST(support_conversations.updated_at,EXCLUDED.updated_at)
  """,nativeQuery=true)
 void mergeIdentity(@Param("oldIdentity") UUID oldIdentity,@Param("newIdentity") UUID newIdentity);

 @Modifying
 @Query("delete from SupportConversation c where c.patientIdentityId=:identity")
 void deleteIdentity(@Param("identity") UUID identity);
}
