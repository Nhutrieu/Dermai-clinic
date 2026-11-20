package com.dermai.appointment;

import java.util.List;
import java.util.UUID;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
class AdminNotificationReadService {
 private final JdbcTemplate jdbc;
 AdminNotificationReadService(JdbcTemplate jdbc){this.jdbc=jdbc;}
 List<String> list(UUID identity) {
  return jdbc.queryForList("select notification_key from appointment.admin_notification_reads where admin_identity_id=? order by read_at desc limit 5000",String.class,identity);
 }
 @Transactional
 void mark(UUID identity,List<String> keys) {
  if(keys.isEmpty())return;
  var rows=keys.stream().distinct().map(key->new Object[]{identity,key}).toList();
  jdbc.batchUpdate("insert into appointment.admin_notification_reads(admin_identity_id,notification_key) values(?,?) on conflict(admin_identity_id,notification_key) do nothing",rows);
 }
}
