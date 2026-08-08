package com.dermai.auth.domain;

import org.springframework.data.jpa.repository.JpaRepository;
import java.util.List;
import java.util.UUID;

public interface StaffAccountEventRepository extends JpaRepository<StaffAccountEvent,UUID> {
 List<StaffAccountEvent> findTop50ByStaffIdentityIdOrderByCreatedAtDesc(UUID staffIdentityId);
}
