package com.dermai.patient;

import org.springframework.data.jpa.repository.JpaRepository;
import java.util.UUID;

interface AiConsentEventRepository extends JpaRepository<AiConsentEvent, UUID> {}
