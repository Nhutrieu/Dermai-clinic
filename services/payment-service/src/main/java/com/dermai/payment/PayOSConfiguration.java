package com.dermai.payment;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.context.annotation.*;
import vn.payos.PayOS;
@Configuration
@ConditionalOnProperty(name="payos.fake-mode",havingValue="false",matchIfMissing=true)
class PayOSConfiguration{
 @Bean PayOS payOS(
   @Value("${payos.client-id}")String clientId,
   @Value("${payos.api-key}")String apiKey,
   @Value("${payos.checksum-key}")String checksumKey){
  return new PayOS(clientId,apiKey,checksumKey);
 }
}



