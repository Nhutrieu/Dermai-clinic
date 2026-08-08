package com.dermai.auth.domain;
import org.springframework.data.jpa.repository.JpaRepository;
import java.util.*;
public interface IdentityRepository extends JpaRepository<Identity,UUID>{Optional<Identity> findByEmailIgnoreCase(String email);Optional<Identity> findByGoogleSubject(String googleSubject);List<Identity> findByRoleOrderByCreatedAtDesc(Identity.Role role);}
