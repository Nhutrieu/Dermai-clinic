package com.dermai.doctor;
import com.fasterxml.jackson.annotation.JsonIgnore;import jakarta.persistence.*;import java.util.*;
@Entity @Table(name="doctors")
public class Doctor{
 @Id public UUID id;@Column(name="identity_id",unique=true) public UUID identityId;@Column(name="full_name",nullable=false) public String fullName;
 @Column(name="specialty_code",nullable=false) public String specialtyCode;@Column(name="experience_years") public int experienceYears;
 @Column(name="certificate_no") public String certificateNo;@Column(name="bio",length=1200) public String bio;@Column(name="avatar_url") public String avatarUrl;@JsonIgnore @Column(name="avatar_data") public byte[] avatarData;@JsonIgnore @Column(name="avatar_mime") public String avatarMime;public boolean active=true;protected Doctor(){}
 public Doctor(UUID identity,String name,String specialty){id=UUID.randomUUID();identityId=identity;fullName=name;specialtyCode=specialty;}
}
