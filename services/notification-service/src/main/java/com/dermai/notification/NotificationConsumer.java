package com.dermai.notification;
import com.fasterxml.jackson.databind.*;import org.springframework.amqp.core.*;import org.springframework.amqp.rabbit.annotation.RabbitListener;import org.springframework.beans.factory.annotation.*;import org.springframework.context.annotation.*;import org.springframework.data.jpa.repository.JpaRepository;import org.springframework.mail.SimpleMailMessage;import org.springframework.mail.javamail.JavaMailSender;import org.springframework.stereotype.Component;import org.springframework.web.client.RestClient;import java.time.Instant;import java.util.Optional;import java.util.UUID;
interface DeliveryRepository extends JpaRepository<Delivery,UUID>{Optional<Delivery> findByEventId(UUID id);}
@Configuration class NotificationMessaging{
 @Bean Queue notificationQueue(){return QueueBuilder.durable("dermai.notifications").withArgument("x-dead-letter-exchange","dermai.notifications.dlx").withArgument("x-dead-letter-routing-key","dermai.notifications").build();}
 @Bean TopicExchange appointmentExchange(){return ExchangeBuilder.topicExchange("dermai.appointments").durable(true).build();}
 @Bean Binding notificationBinding(@Qualifier("notificationQueue") Queue q,TopicExchange e){return BindingBuilder.bind(q).to(e).with("Appointment*");}
 @Bean DirectExchange deadExchange(){return ExchangeBuilder.directExchange("dermai.notifications.dlx").durable(true).build();}
 @Bean Queue deadQueue(){return QueueBuilder.durable("dermai.notifications.dead").build();}
 @Bean Binding deadBinding(@Qualifier("deadQueue") Queue deadQueue,DirectExchange deadExchange){return BindingBuilder.bind(deadQueue).to(deadExchange).with("dermai.notifications");}
}
@Component class NotificationConsumer{
 private final DeliveryRepository repo;private final JavaMailSender mail;private final RestClient auth;private final ObjectMapper json;private final String token;
 NotificationConsumer(DeliveryRepository r,JavaMailSender m,ObjectMapper j,@Value("${services.auth-url}") String url,@Value("${services.token}") String token){repo=r;mail=m;json=j;auth=RestClient.builder().baseUrl(url).build();this.token=token;}
 @RabbitListener(queues="dermai.notifications")
 public void consume(String payload)throws Exception{
  JsonNode e=json.readTree(payload);UUID eventId=UUID.fromString(e.path("eventId").asText());var existing=repo.findByEventId(eventId);if(existing.isPresent()&&existing.get().sentAt!=null)return;
  UUID identity=UUID.fromString(e.path("patientIdentityId").asText());var owner=auth.get().uri("/api/v1/auth/internal/identities/{id}",identity).header("X-Service-Token",token).retrieve().body(Identity.class);
  if(owner==null)throw new IllegalStateException("Không tìm thấy người nhận");
  String status=e.path("status").asText(),start=e.path("startAt").asText();var d=existing.orElseGet(()->{var n=new Delivery();n.id=UUID.randomUUID();n.eventId=eventId;n.eventType=status;n.recipient=owner.email();n.subject=subject(status);return n;});d.attempts++;repo.save(d);
  try{var msg=new SimpleMailMessage();msg.setTo(owner.email());msg.setFrom("no-reply@dermai.local");msg.setSubject(d.subject);msg.setText("Trạng thái lịch khám: "+status+"\nThời gian: "+start+"\n\nDermAI chỉ hỗ trợ quản lý, không thay thế bác sĩ.");mail.send(msg);d.sentAt=Instant.now();d.lastError=null;repo.save(d);}
  catch(RuntimeException ex){d.lastError=String.valueOf(ex.getMessage());repo.save(d);throw ex;}
 }
 private String subject(String s){return switch(s){case"CANCELLED"->"Lịch khám đã hủy";case"COMPLETED"->"Đã hoàn thành khám";case"FOLLOW_UP_REQUIRED"->"Yêu cầu tái khám";default->"Cập nhật lịch khám DermAI";};}
 record Identity(UUID identityId,String email,String role){}
}
