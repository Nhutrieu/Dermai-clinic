package com.dermai.prescription;
import com.fasterxml.jackson.databind.ObjectMapper;import java.math.BigDecimal;import java.util.UUID;import org.springframework.amqp.core.*;import org.springframework.amqp.rabbit.annotation.RabbitListener;import org.springframework.beans.factory.annotation.Qualifier;import org.springframework.context.annotation.*;import org.springframework.stereotype.Component;
@Configuration class BillingMessagingConfiguration{
 @Bean TopicExchange billingEventsExchange(){return ExchangeBuilder.topicExchange("booking_events").durable(true).build();}
 @Bean Queue invoicePaymentQueue(){return QueueBuilder.durable("dermai.invoice-payments").build();}
 @Bean Binding invoicePaidBinding(@Qualifier("invoicePaymentQueue")Queue queue,@Qualifier("billingEventsExchange")TopicExchange exchange){return BindingBuilder.bind(queue).to(exchange).with("invoice.paid");}
}
@Component class InvoicePaymentConsumer{
 private final BillingService billing;private final ObjectMapper json;InvoicePaymentConsumer(BillingService billing,ObjectMapper json){this.billing=billing;this.json=json;}
 @RabbitListener(queues="dermai.invoice-payments") public void consume(String payload)throws Exception{var event=json.readTree(payload);billing.markOnlinePaid(UUID.fromString(event.path("invoiceId").asText()),new BigDecimal(event.path("amount").asText()));}
}