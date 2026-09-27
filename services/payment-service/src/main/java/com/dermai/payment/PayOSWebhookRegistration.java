package com.dermai.payment;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.stereotype.Component;

@Component
class PayOSWebhookRegistration {
 private static final Logger log=LoggerFactory.getLogger(PayOSWebhookRegistration.class);
 private final PayOSGateway payOS;
 private final String webhookUrl;
 PayOSWebhookRegistration(PayOSGateway payOS,@Value("${payment.webhook-url:}")String webhookUrl){this.payOS=payOS;this.webhookUrl=webhookUrl;}
 @EventListener(ApplicationReadyEvent.class)
 void register(){
  if(webhookUrl==null||webhookUrl.isBlank()){log.warn("PAYOS_WEBHOOK_URL is empty; automatic webhook registration is disabled.");return;}
  try{payOS.confirmWebhook(webhookUrl);log.info("payOS webhook registered successfully: {}",webhookUrl);}
  catch(RuntimeException error){log.error("Could not register payOS webhook URL {}",webhookUrl,error);}
 }
}