package com.dermai.appointment;
import org.springframework.data.jpa.repository.*;import org.springframework.data.repository.query.Param;import jakarta.persistence.LockModeType;import java.time.*;import java.util.*;
public interface AppointmentRepository extends JpaRepository<Appointment,UUID>{
 Optional<Appointment> findByIdempotencyKey(String key);
 List<Appointment> findByPatientIdOrderByStartAtDesc(UUID patient);
 List<Appointment> findByPatientIdentityIdOrderByStartAtDesc(UUID identity);
 boolean existsByPatientIdentityIdAndStatusIn(UUID identity,Collection<AppointmentStatus> statuses);
 List<Appointment> findByDoctorIdAndStartAtBetweenOrderByStartAt(UUID doctor,Instant from,Instant to);
 List<Appointment> findByDoctorIdentityIdAndStartAtBetweenOrderByStartAt(UUID identity,Instant from,Instant to);
 List<Appointment> findByStatusInAndStartAtBetweenOrderByStartAt(Collection<AppointmentStatus> statuses,Instant from,Instant to);
 List<Appointment> findByStatusInAndEndAtBefore(Collection<AppointmentStatus> statuses,Instant cutoff);
 List<Appointment> findByStatusAndHoldExpiresAtBefore(AppointmentStatus status,Instant cutoff);
 List<Appointment> findByStatusAndStartAtBetween(AppointmentStatus status,Instant from,Instant to);
 @Query("select a from Appointment a where a.status <> com.dermai.appointment.AppointmentStatus.CANCELLED and a.startAt < :to and a.endAt > :from")
 List<Appointment> findActiveOverlapping(@Param("from") Instant from,@Param("to") Instant to);
 @Lock(LockModeType.PESSIMISTIC_WRITE) @Query("select a from Appointment a where a.id=:id") Optional<Appointment> findLocked(@Param("id") UUID id);
 @Modifying @Query("update Appointment a set a.patientIdentityId=:newIdentity where a.patientId=:patientId and a.patientIdentityId=:oldIdentity") int relinkPatientIdentity(@Param("patientId") UUID patientId,@Param("oldIdentity") UUID oldIdentity,@Param("newIdentity") UUID newIdentity);
}
