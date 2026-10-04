package com.dermai.prescription;

import jakarta.persistence.*;
import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name="inventory_movements")
public class InventoryMovement {
 @Id public UUID id;
 @Column(name="invoice_id",nullable=false) public UUID invoiceId;
 @Column(name="medicine_id",nullable=false) public UUID medicineId;
 @Column(name="quantity_delta",nullable=false) public int quantityDelta;
 @Column(name="performed_by",nullable=false) public UUID performedBy;
 @Column(name="created_at",nullable=false) public Instant createdAt;
 @Column(nullable=false,length=40) public String reason;
 protected InventoryMovement(){}
}