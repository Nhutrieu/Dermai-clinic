package com.dermai.notification;
import org.springframework.amqp.core.*;
import org.springframework.amqp.rabbit.annotation.RabbitListener;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.context.annotation.*;
import org.springframework.stereotype.Component;

@Configuration class PaymentNotificationMessaging{
 @Bean TopicExchange bookingEventsExchange(){return ExchangeBuilder.topicExchange("booking_events").durable(true).build();}
 @Bean Queue paymentNotificationQueue(){return QueueBuilder.durable("dermai.notifications.payments").build();}
 @Bean Binding paymentNotificationBinding(@Qualifier("paymentNotificationQueue")Queue queue,@Qualifier("bookingEventsExchange")TopicExchange exchange){return BindingBuilder.bind(queue).to(exchange).with("booking.paid");}
 @Bean Binding paymentLinkNotificationBinding(@Qualifier("paymentNotificationQueue")Queue queue,@Qualifier("bookingEventsExchange")TopicExchange exchange){return BindingBuilder.bind(queue).to(exchange).with("payment.link_created");}
 @Bean Binding refundNotificationBinding(@Qualifier("paymentNotificationQueue")Queue queue,@Qualifier("bookingEventsExchange")TopicExchange exchange){return BindingBuilder.bind(queue).to(exchange).with("payment.refunded");}
}
@Component class PaymentNotificationConsumer{
 private final NotificationConsumer notifications;
 PaymentNotificationConsumer(NotificationConsumer notifications){this.notifications=notifications;}
 @RabbitListener(queues="dermai.notifications.payments") public void consume(String payload)throws Exception{notifications.consume(payload);}
}



