package com.dermai.appointment;
import org.springframework.data.jpa.repository.JpaRepository;import java.util.*;
interface ClinicReviewRepository extends JpaRepository<ClinicReview,UUID>{Optional<ClinicReview> findByAppointmentId(UUID appointmentId);List<ClinicReview> findTop6ByStatusOrderByCreatedAtDesc(ClinicReview.Status status);List<ClinicReview> findAllByOrderByCreatedAtDesc();}
