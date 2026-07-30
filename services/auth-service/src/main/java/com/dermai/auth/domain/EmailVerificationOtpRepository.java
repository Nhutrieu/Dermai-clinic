package com.dermai.auth.domain;

import java.util.Optional;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;

public interface EmailVerificationOtpRepository extends JpaRepository<EmailVerificationOtp,UUID> {
 Optional<EmailVerificationOtp> findTopByIdentityIdOrderByCreatedAtDesc(UUID identityId);
}
