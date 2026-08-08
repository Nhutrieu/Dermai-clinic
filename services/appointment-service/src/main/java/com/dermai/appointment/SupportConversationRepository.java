package com.dermai.appointment;

import org.springframework.data.jpa.repository.*;
import org.springframework.data.repository.query.Param;
import java.util.*;

interface SupportConversationRepository extends JpaRepository<SupportConversation,UUID> {
 List<SupportConversation> findAllByOrderByUpdatedAtDesc();

 @Modifying
 @Query(value="""
  INSERT INTO support_conversations(patient_identity_id,assigned_receptionist_identity_id,assigned_at,updated_at)
  VALUES (:patient,:receptionist,now(),now())
  ON CONFLICT (patient_identity_id) DO UPDATE
  SET assigned_receptionist_identity_id=EXCLUDED.assigned_receptionist_identity_id,
      assigned_at=now(),updated_at=now()
  WHERE support_conversations.assigned_receptionist_identity_id IS NULL
     OR support_conversations.assigned_receptionist_identity_id=EXCLUDED.assigned_receptionist_identity_id
  """,nativeQuery=true)
 int claim(@Param("patient") UUID patientIdentityId,@Param("receptionist") UUID receptionistIdentityId);

 @Modifying
 @Query("update SupportConversation c set c.assignedReceptionistIdentityId=null,c.assignedAt=null,c.updatedAt=CURRENT_TIMESTAMP where c.patientIdentityId=:patient and c.assignedReceptionistIdentityId=:receptionist")
 int release(@Param("patient") UUID patientIdentityId,@Param("receptionist") UUID receptionistIdentityId);

 @Modifying
 @Query(value="""
  INSERT INTO support_conversations(patient_identity_id,updated_at)
  VALUES (:patient,now())
  ON CONFLICT (patient_identity_id) DO UPDATE SET updated_at=now()
  """,nativeQuery=true)
 void touch(@Param("patient") UUID patientIdentityId);

 @Modifying
 @Query(value="""
  INSERT INTO support_conversations(patient_identity_id,assigned_receptionist_identity_id,assigned_at,updated_at)
  SELECT :newIdentity,assigned_receptionist_identity_id,assigned_at,updated_at
  FROM support_conversations WHERE patient_identity_id=:oldIdentity
  ON CONFLICT (patient_identity_id) DO UPDATE
  SET assigned_receptionist_identity_id=COALESCE(support_conversations.assigned_receptionist_identity_id,EXCLUDED.assigned_receptionist_identity_id),
      assigned_at=COALESCE(support_conversations.assigned_at,EXCLUDED.assigned_at),
      updated_at=GREATEST(support_conversations.updated_at,EXCLUDED.updated_at)
  """,nativeQuery=true)
 void mergeIdentity(@Param("oldIdentity") UUID oldIdentity,@Param("newIdentity") UUID newIdentity);

 @Modifying
 @Query("delete from SupportConversation c where c.patientIdentityId=:identity")
 void deleteIdentity(@Param("identity") UUID identity);
}
