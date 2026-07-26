package com.dermai.doctor;
import org.springframework.data.jpa.repository.JpaRepository;import java.util.*;
interface DoctorRepository extends JpaRepository<Doctor,UUID>{Optional<Doctor> findByIdentityId(UUID id);List<Doctor> findBySpecialtyCodeAndActiveTrue(String code);}
interface ScheduleRepository extends JpaRepository<WorkSchedule,UUID>{List<WorkSchedule> findByDoctorId(UUID id);}
interface LeaveRepository extends JpaRepository<LeavePeriod,UUID>{List<LeavePeriod> findByDoctorId(UUID id);}
