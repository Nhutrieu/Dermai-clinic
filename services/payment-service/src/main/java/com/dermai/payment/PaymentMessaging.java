package com.dermai.payment;
import java.time.Instant;
import org.springframework.amqp.core.*;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.context.annotation.*;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

@Configuration class PaymentMessagingConfiguration{
 static final String EXCHANGE="booking_events";
 @Bean TopicExchange bookingEventsExchange(){return ExchangeBuilder.topicExchange(EXCHANGE).durable(true).build();}
}

@Component class PaymentOutboxPublisher{
 private final PaymentOutboxRepository outbox;private final RabbitTemplate rabbit;
 PaymentOutboxPublisher(PaymentOutboxRepository outbox,RabbitTemplate rabbit){this.outbox=outbox;this.rabbit=rabbit;}
 @Scheduled(fixedDelayString="${outbox.delay-ms:1000}") @Transactional
 public void publish(){
  for(var event:outbox.findTop100ByPublishedAtIsNullOrderByCreatedAt()){
   rabbit.convertAndSend(PaymentMessagingConfiguration.EXCHANGE,event.routingKey,event.payload,message->{
    message.getMessageProperties().setMessageId(event.id.toString());
    message.getMessageProperties().setContentType("application/json");
    return message;
   });
   event.publishedAt=Instant.now();
  }
 }
}


