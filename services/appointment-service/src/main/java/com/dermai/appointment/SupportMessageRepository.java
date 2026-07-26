package com.dermai.appointment;
import org.springframework.data.jpa.repository.JpaRepository;import java.util.*;
interface SupportMessageRepository extends JpaRepository<SupportMessage,UUID>{List<SupportMessage> findByPatientIdentityIdOrderBySentAtAsc(UUID patientIdentityId);List<SupportMessage> findAllByOrderBySentAtAsc();}
