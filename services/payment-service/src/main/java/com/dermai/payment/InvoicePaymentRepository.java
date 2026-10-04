package com.dermai.payment;
import java.util.*;import org.springframework.data.jpa.repository.JpaRepository;
interface InvoicePaymentRepository extends JpaRepository<InvoicePayment,UUID>{Optional<InvoicePayment> findByInvoiceId(UUID invoiceId);Optional<InvoicePayment> findByOrderCode(long orderCode);List<InvoicePayment> findTop100ByStatusInOrderByUpdatedAtAsc(Collection<PaymentStatus> statuses);}
