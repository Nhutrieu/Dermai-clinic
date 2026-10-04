package com.dermai.prescription;

import jakarta.persistence.*;
import java.math.BigDecimal;
import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name="medicines")
public class Medicine {
 @Id public UUID id;
 @Column(nullable=false,unique=true,length=60) public String sku;
 @Column(nullable=false,length=200) public String name;
 @Column(nullable=false,length=40) public String unit;
 @Column(name="sale_price",nullable=false,precision=12,scale=0) public BigDecimal salePrice;
 @Column(name="stock_quantity",nullable=false) public int stockQuantity;
 @Column(nullable=false) public boolean active=true;
 @Column(name="updated_at",nullable=false) public Instant updatedAt=Instant.now();
 @Version public long version;
 protected Medicine(){}
}