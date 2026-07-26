package com.dermai.auth.domain;
import org.springframework.data.jpa.repository.JpaRepository;
import java.util.*;
public interface RefreshTokenRepository extends JpaRepository<RefreshToken,UUID>{
 Optional<RefreshToken> findByTokenHash(String hash);
 java.util.List<RefreshToken> findAllByIdentityId(UUID identityId);
}
