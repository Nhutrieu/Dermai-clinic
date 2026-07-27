package com.dermai.appointment;
import org.springframework.data.jpa.repository.JpaRepository;import java.time.*;import java.util.*;
interface ClinicClosureRepository extends JpaRepository<ClinicClosure,UUID>{boolean existsByClosureDate(LocalDate date);Optional<ClinicClosure> findByClosureDate(LocalDate date);List<ClinicClosure> findAllByOrderByClosureDateAsc();}
interface AppointmentNotificationRepository extends JpaRepository<AppointmentNotification,UUID>{List<AppointmentNotification> findTop50ByPatientIdentityIdOrderByCreatedAtDesc(UUID identity);boolean existsByAppointmentIdAndNotificationType(UUID appointment,String type);}
interface ReminderActionRepository extends JpaRepository<ReminderAction,UUID>{Optional<ReminderAction> findTopByAppointmentIdOrderByCreatedAtDesc(UUID appointment);}
