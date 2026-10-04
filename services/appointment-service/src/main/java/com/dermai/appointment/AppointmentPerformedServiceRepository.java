package com.dermai.appointment;

import java.util.*;
import org.springframework.data.jpa.repository.*;
import org.springframework.data.repository.query.Param;

public interface AppointmentPerformedServiceRepository extends JpaRepository<AppointmentPerformedService,UUID> {
 List<AppointmentPerformedService> findByAppointmentIdOrderByServiceNameAsc(UUID appointmentId);
 @Modifying @Query("delete from AppointmentPerformedService s where s.appointmentId=:appointmentId")
 int deleteForAppointment(@Param("appointmentId") UUID appointmentId);
}
