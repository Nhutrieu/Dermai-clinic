package com.dermai.appointment;
import org.springframework.amqp.core.*;import org.springframework.amqp.rabbit.core.RabbitTemplate;import org.springframework.context.annotation.*;import org.springframework.scheduling.annotation.Scheduled;import org.springframework.stereotype.Component;import org.springframework.transaction.annotation.Transactional;import java.time.Instant;
@Configuration class AppointmentMessaging{
 static final String EXCHANGE="dermai.appointments";
 @Bean TopicExchange appointmentExchange(){return ExchangeBuilder.topicExchange(EXCHANGE).durable(true).build();}
}
@Component class OutboxPublisher{
 private final OutboxRepository repo;private final RabbitTemplate rabbit;
 OutboxPublisher(OutboxRepository r,RabbitTemplate t){repo=r;rabbit=t;}
 @Scheduled(fixedDelayString="${outbox.delay-ms:1000}") @Transactional
 public void publish(){
  for(var event:repo.findTop100ByPublishedAtIsNullOrderByCreatedAt()){
   rabbit.convertAndSend(AppointmentMessaging.EXCHANGE,event.eventType,event.payload,m->{m.getMessageProperties().setMessageId(event.id.toString());m.getMessageProperties().setContentType("application/json");return m;});
   event.publishedAt=Instant.now();
  }
 }
}
