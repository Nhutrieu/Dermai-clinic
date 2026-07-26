package com.dermai.appointment;
import org.springframework.data.jpa.repository.JpaRepository;import java.util.*;
interface OutboxRepository extends JpaRepository<OutboxEvent,UUID>{List<OutboxEvent> findTop100ByPublishedAtIsNullOrderByCreatedAt();}
