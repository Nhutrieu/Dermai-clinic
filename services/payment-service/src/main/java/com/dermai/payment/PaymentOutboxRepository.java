package com.dermai.payment;
import java.util.*;
import org.springframework.data.jpa.repository.JpaRepository;
interface PaymentOutboxRepository extends JpaRepository<PaymentOutboxEvent,UUID>{List<PaymentOutboxEvent> findTop100ByPublishedAtIsNullOrderByCreatedAt();}

