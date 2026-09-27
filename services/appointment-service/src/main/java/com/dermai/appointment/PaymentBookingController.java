package com.dermai.appointment;
import java.time.Instant;
import java.util.UUID;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.*;
import org.springframework.web.bind.annotation.*;

@RestController @RequestMapping("/api/v1/appointments/internal")
class PaymentBookingController{
 private final AppointmentService service;private final String serviceToken;
 PaymentBookingController(AppointmentService service,@Value("${security.service-token}")String serviceToken){this.service=service;this.serviceToken=serviceToken;}
 record PreparePayment(UUID patientIdentityId){}
 record PaymentBooking(UUID id,UUID patientIdentityId,Instant startAt,AppointmentStatus status,String cancelReason,String cancellationInitiator){}
 @PostMapping("/{id}/prepare-payment") PaymentBooking prepare(@PathVariable UUID id,@RequestHeader("X-Service-Token")String token,@RequestBody PreparePayment body){
  if(serviceToken.isBlank()||!serviceToken.equals(token))throw new AppointmentController.Forbidden();
  var booking=service.preparePayment(id,body.patientIdentityId());
  return response(booking);
 }
 @GetMapping("/{id}") PaymentBooking get(@PathVariable UUID id,@RequestHeader("X-Service-Token")String token){
  if(serviceToken.isBlank()||!serviceToken.equals(token))throw new AppointmentController.Forbidden();
  return response(service.find(id));
 }
 private PaymentBooking response(Appointment booking){return new PaymentBooking(booking.id,booking.patientIdentityId,booking.startAt,booking.status,booking.cancelReason,booking.cancellationInitiator);}
}






