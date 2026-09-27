package com.dermai.payment;
import static org.assertj.core.api.Assertions.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import org.junit.jupiter.api.Test;
import vn.payos.PayOS;

class PayOSClientAdapterTest{
 @Test void verifiesThePayOSWebhookHmacOverAlphabeticallySortedData()throws Exception{
  String key="test-checksum-key";
  var data=new LinkedHashMap<String,Object>();
  data.put("orderCode",123456L);data.put("amount",100000L);data.put("description","DERMAI 123456");
  data.put("accountNumber","12345678");data.put("reference","TF230204212323");data.put("transactionDateTime","2026-09-21 10:00:00");
  data.put("currency","VND");data.put("paymentLinkId","pay-link-id");data.put("code","00");data.put("desc","Thành công");
  data.put("counterAccountBankId","");data.put("counterAccountBankName","");data.put("counterAccountName","");data.put("counterAccountNumber","");
  data.put("virtualAccountName","");data.put("virtualAccountNumber","");
  var payload=new LinkedHashMap<String,Object>();payload.put("code","00");payload.put("desc","success");payload.put("success",true);payload.put("data",data);payload.put("signature",signature(data,key));
  var adapter=new PayOSClientAdapter(new PayOS("client","api",key));

  var verified=adapter.verify(payload);

  assertThat(verified.orderCode()).isEqualTo(123456L);
  assertThat(verified.amount()).isEqualTo(100000L);
  assertThat(verified.reference()).isEqualTo("TF230204212323");
 }

 @Test void rejectsAnInvalidWebhookSignature(){
  var payload=Map.<String,Object>of("code","00","desc","success","success",true,"data",Map.of(),"signature","tampered");
  var adapter=new PayOSClientAdapter(new PayOS("client","api","checksum"));
  assertThatThrownBy(()->adapter.verify(payload)).isInstanceOf(RuntimeException.class);
 }

 private String signature(Map<String,Object> data,String key)throws Exception{
  var sorted=new TreeMap<>(data);var canonical=new StringJoiner("&");sorted.forEach((name,value)->canonical.add(name+"="+(value==null?"":value)));
  var hmac=Mac.getInstance("HmacSHA256");hmac.init(new SecretKeySpec(key.getBytes(StandardCharsets.UTF_8),"HmacSHA256"));
  var result=new StringBuilder();for(byte value:hmac.doFinal(canonical.toString().getBytes(StandardCharsets.UTF_8)))result.append(String.format("%02x",value));
  return result.toString();
 }
}





