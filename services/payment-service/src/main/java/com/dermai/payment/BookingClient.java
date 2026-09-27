package com.dermai.payment;
import java.time.Instant;
import java.util.UUID;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

@Component class BookingClient{
 private final RestClient client;private final String token;
 BookingClient(RestClient.Builder builder,@Value("${services.appointment-url}")String url,@Value("${services.token}")String token){
  client=builder.baseUrl(url).build();this.token=token;
 }
 BookingDetails preparePayment(UUID bookingId,UUID patientIdentityId){
  var result=client.post()
    .uri("/api/v1/appointments/internal/{id}/prepare-payment",bookingId)
    .header("X-Service-Token",token)
    .body(new PreparePayment(patientIdentityId))
    .retrieve().body(BookingDetails.class);
  if(result==null)throw new IllegalStateException("EMPTY_BOOKING_RESPONSE");
  return result;
 }
 BookingDetails get(UUID bookingId){
  var result=client.get()
    .uri("/api/v1/appointments/internal/{id}",bookingId)
    .header("X-Service-Token",token)
    .retrieve().body(BookingDetails.class);
  if(result==null)throw new IllegalStateException("EMPTY_BOOKING_RESPONSE");
  return result;
 }
 record PreparePayment(UUID patientIdentityId){}
 record BookingDetails(UUID id,UUID patientIdentityId,Instant startAt,String status,String cancelReason,String cancellationInitiator){}
}

