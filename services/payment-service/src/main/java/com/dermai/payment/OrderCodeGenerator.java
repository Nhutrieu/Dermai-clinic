package com.dermai.payment;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;
@Component class OrderCodeGenerator{
 private final JdbcTemplate jdbc;
 OrderCodeGenerator(JdbcTemplate jdbc){this.jdbc=jdbc;}
 long next(){return jdbc.queryForObject("select nextval('payment_order_code_seq')",Long.class);}
}

