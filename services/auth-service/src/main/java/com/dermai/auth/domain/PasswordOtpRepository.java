package com.dermai.auth.domain;
import org.springframework.data.jpa.repository.JpaRepository;
import java.util.*;
public interface PasswordOtpRepository extends JpaRepository<PasswordOtp,UUID>{Optional<PasswordOtp> findTopByIdentityIdOrderByExpiresAtDesc(UUID id);}
