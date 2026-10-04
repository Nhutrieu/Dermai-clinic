package com.dermai.prescription;

import jakarta.persistence.LockModeType;
import java.time.Instant;
import java.util.*;
import org.springframework.data.jpa.repository.*;
import org.springframework.data.repository.query.Param;

interface MedicineRepository extends JpaRepository<Medicine,UUID>{
 Optional<Medicine> findBySkuIgnoreCase(String sku);
 List<Medicine> findByActiveTrueOrderByName();
 @Query(value="select coalesce((select product.active from pharmacy.products product where product.id=:id), true)",nativeQuery=true) boolean isClinicSaleActive(@Param("id")UUID id);
 @Lock(LockModeType.PESSIMISTIC_WRITE) @Query("select m from Medicine m where m.id=:id") Optional<Medicine> findLockedById(@Param("id")UUID id);
}
interface InvoiceRepository extends JpaRepository<Invoice,UUID>{
 Optional<Invoice> findByAppointmentId(UUID appointmentId);
 List<Invoice> findByPatientIdentityIdOrderByCreatedAtDesc(UUID patientIdentityId);
 List<Invoice> findTop100ByOrderByCreatedAtDesc();
 List<Invoice> findByCreatedAtBetweenOrderByCreatedAtDesc(Instant from,Instant to);
 List<Invoice> findByPaidAtBetweenOrderByPaidAtDesc(Instant from,Instant to);
}
interface InvoiceCashPaymentRepository extends JpaRepository<InvoiceCashPayment,UUID>{Optional<InvoiceCashPayment> findByInvoiceId(UUID invoiceId);}
interface InventoryMovementRepository extends JpaRepository<InventoryMovement,UUID>{boolean existsByInvoiceId(UUID invoiceId);}
interface InvoiceAdjustmentRepository extends JpaRepository<InvoiceAdjustment,UUID>{List<InvoiceAdjustment> findByInvoiceIdOrderByCreatedAtDesc(UUID invoiceId);}
