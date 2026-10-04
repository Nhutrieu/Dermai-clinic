package com.dermai.appointment;

import jakarta.validation.Valid;
import jakarta.validation.constraints.Size;
import java.util.*;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;

@RestController
@RequestMapping("/api/v1/appointments/{appointmentId}/performed-services")
public class AppointmentPerformedServiceController {
 private final AppointmentPerformedServiceService services;
 AppointmentPerformedServiceController(AppointmentPerformedServiceService services){this.services=services;}
 record Update(@Size(max=50) Set<UUID> serviceIds){}
 @GetMapping AppointmentPerformedServiceService.View get(@PathVariable UUID appointmentId,@RequestHeader("X-User-Id") UUID identity,@RequestHeader("X-User-Role") String role){return services.get(appointmentId,identity,role);}
 @PutMapping AppointmentPerformedServiceService.View confirm(@PathVariable UUID appointmentId,@RequestHeader("X-User-Id") UUID identity,@RequestHeader("X-User-Role") String role,@Valid @RequestBody Update body){if(!"DOCTOR".equals(role))throw new ResponseStatusException(HttpStatus.FORBIDDEN);return services.confirm(appointmentId,body.serviceIds(),identity);}
}
