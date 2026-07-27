package com.dermai.patient;
import org.springframework.data.domain.*;import org.springframework.data.jpa.repository.JpaRepository;import java.util.*;
public interface PatientRepository extends JpaRepository<Patient,UUID>{Optional<Patient> findByIdentityId(UUID id);Optional<Patient> findFirstByPhone(String phone);Page<Patient> findByFullNameContainingIgnoreCaseOrPhoneContaining(String name,String phone,Pageable pageable);}
