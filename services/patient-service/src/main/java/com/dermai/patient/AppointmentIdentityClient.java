package com.dermai.patient;

import java.util.Map;
import java.util.UUID;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;
import org.springframework.web.server.ResponseStatusException;

@Component
class AppointmentIdentityClient {
 private final RestClient client;
 private final String serviceToken;

 AppointmentIdentityClient(RestClient.Builder builder,@Value("${services.appointment-url}") String url,@Value("${services.token}") String token){
  client=builder.baseUrl(url).build();serviceToken=token;
 }

 void relink(UUID patientId,UUID oldIdentityId,UUID newIdentityId){
  if(serviceToken==null||serviceToken.isBlank())throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE,"Chưa cấu hình SERVICE_TOKEN để liên kết hồ sơ hotline.");
  try{
   client.patch().uri("/api/v1/appointments/internal/patient-identities")
    .header("X-Service-Token",serviceToken)
    .body(Map.of("patientId",patientId,"oldIdentityId",oldIdentityId,"newIdentityId",newIdentityId))
    .retrieve().toBodilessEntity();
  }catch(Exception error){
   throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE,"Chưa thể đồng bộ lịch cũ của hồ sơ hotline. Vui lòng thử lại.",error);
  }
 }
}
