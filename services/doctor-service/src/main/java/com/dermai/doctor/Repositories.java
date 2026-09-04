package com.dermai.doctor;
import org.springframework.data.jpa.repository.JpaRepository;import java.util.*;
interface DoctorRepository extends JpaRepository<Doctor,UUID>{Optional<Doctor> findByIdentityId(UUID id);List<Doctor> findBySpecialtyCodeAndActiveTrue(String code);}
interface ScheduleRepository extends JpaRepository<WorkSchedule,UUID>{List<WorkSchedule> findByDoctorId(UUID id);}
interface SlotDurationPolicyRepository extends JpaRepository<SlotDurationPolicy,UUID>{List<SlotDurationPolicy> findByDoctorIdOrderByEffectiveFromAsc(UUID id);Optional<SlotDurationPolicy> findByDoctorIdAndEffectiveFrom(UUID id,java.time.LocalDate effectiveFrom);}
interface LeaveRepository extends JpaRepository<LeavePeriod,UUID>{List<LeavePeriod> findByDoctorId(UUID id);List<LeavePeriod> findByStatusOrderByStartAtAsc(String status);List<LeavePeriod> findByStatusAndReviewedAtAfterOrderByReviewedAtDesc(String status,java.time.Instant reviewedAt);}
interface LeaveApprovalViewRepository extends JpaRepository<LeaveApprovalView,UUID>{List<LeaveApprovalView> findByReceptionistIdentityIdAndLeaveIdIn(UUID receptionistIdentityId,Collection<UUID> leaveIds);Optional<LeaveApprovalView> findByLeaveIdAndReceptionistIdentityId(UUID leaveId,UUID receptionistIdentityId);}
