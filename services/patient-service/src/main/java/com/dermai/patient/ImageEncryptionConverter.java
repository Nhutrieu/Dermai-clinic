package com.dermai.patient;

import jakarta.persistence.AttributeConverter;
import jakarta.persistence.Converter;
import javax.crypto.Cipher;
import javax.crypto.spec.GCMParameterSpec;
import javax.crypto.spec.SecretKeySpec;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.util.Arrays;
import java.util.Base64;

@Converter
public class ImageEncryptionConverter implements AttributeConverter<byte[], byte[]> {
  private static final byte[] MAGIC = new byte[]{'D', 'A', 'I', '1'};
  private static final int IV_BYTES = 12;
  private static final SecureRandom RANDOM = new SecureRandom();
  private static final String LOCAL_ONLY_KEY = "dermai-local-development-key-change-me";
  private final SecretKeySpec key = new SecretKeySpec(resolveKey(), "AES");

  @Override
  public byte[] convertToDatabaseColumn(byte[] plain) {
    if (plain == null || plain.length == 0) return plain;
    try {
      byte[] iv = new byte[IV_BYTES];
      RANDOM.nextBytes(iv);
      Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
      cipher.init(Cipher.ENCRYPT_MODE, key, new GCMParameterSpec(128, iv));
      byte[] encrypted = cipher.doFinal(plain);
      return ByteBuffer.allocate(MAGIC.length + iv.length + encrypted.length)
          .put(MAGIC).put(iv).put(encrypted).array();
    } catch (Exception error) {
      throw new IllegalStateException("Could not encrypt the medical image.", error);
    }
  }

  @Override
  public byte[] convertToEntityAttribute(byte[] stored) {
    if (stored == null || stored.length == 0 || !hasMagic(stored)) return stored;
    try {
      byte[] iv = Arrays.copyOfRange(stored, MAGIC.length, MAGIC.length + IV_BYTES);
      byte[] encrypted = Arrays.copyOfRange(stored, MAGIC.length + IV_BYTES, stored.length);
      Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
      cipher.init(Cipher.DECRYPT_MODE, key, new GCMParameterSpec(128, iv));
      return cipher.doFinal(encrypted);
    } catch (Exception error) {
      throw new IllegalStateException("Could not decrypt the medical image.", error);
    }
  }

  private boolean hasMagic(byte[] value) {
    return value.length > MAGIC.length + IV_BYTES
        && value[0] == MAGIC[0] && value[1] == MAGIC[1]
        && value[2] == MAGIC[2] && value[3] == MAGIC[3];
  }

  private byte[] resolveKey() {
    try {
      String environmentValue = System.getenv("DATA_ENCRYPTION_KEY");
      String configured = environmentValue == null ? LOCAL_ONLY_KEY : environmentValue.trim();
      if (configured.isEmpty()) throw new IllegalStateException("DATA_ENCRYPTION_KEY must not be empty.");
      if (configured.startsWith("base64:")) {
        byte[] decoded = Base64.getDecoder().decode(configured.substring("base64:".length()));
        if (decoded.length != 32) throw new IllegalStateException("DATA_ENCRYPTION_KEY must decode to 32 bytes.");
        return decoded;
      }
      return MessageDigest.getInstance("SHA-256").digest(configured.getBytes(StandardCharsets.UTF_8));
    } catch (IllegalStateException error) {
      throw error;
    } catch (Exception error) {
      throw new IllegalStateException("Could not initialize the image encryption key.", error);
    }
  }
}
