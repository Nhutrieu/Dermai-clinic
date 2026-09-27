package com.dermai.payment;
import jakarta.persistence.LockModeType;
import java.time.Instant;
import java.util.*;
import org.springframework.data.jpa.repository.*;
interface PaymentRepository extends JpaRepository<Payment, UUID>{
 Optional<Payment> findByBookingIdAndPatientIdentityId(UUID bookingId,UUID patientIdentityId);
 Optional<Payment> findByBookingId(UUID bookingId);
 @Lock(LockModeType.PESSIMISTIC_WRITE)
 Optional<Payment> findLockedByBookingId(UUID bookingId);
 @Lock(LockModeType.PESSIMISTIC_WRITE)
 Optional<Payment> findByOrderCode(Long orderCode);
 @Override @Lock(LockModeType.PESSIMISTIC_WRITE)
 Optional<Payment> findById(UUID id);
 @Query("select p from Payment p where p.id = :id")
 Optional<Payment> findUnlockedById(UUID id);
 List<Payment> findTop100ByStatusInOrderByUpdatedAtAsc(Collection<PaymentStatus> statuses);
 List<Payment> findTop100ByStatusInAndExpiresAtLessThanEqualOrderByExpiresAtAsc(Collection<PaymentStatus> statuses,Instant now);
 List<Payment> findTop100ByStatusInOrderByRefundRequestedAtDesc(Collection<PaymentStatus> statuses);
}
