ALTER TABLE clinic_services ADD COLUMN specialty_code VARCHAR(80);

UPDATE clinic_services SET specialty_code = CASE code
    WHEN 'ACNE' THEN 'DA LIỄU - ĐIỀU TRỊ MỤN'
    WHEN 'PIGMENT' THEN 'DA LIỄU THẨM MỸ.'
    WHEN 'REJUVENATION' THEN 'DA LIỄU THẨM MỸ.'
    ELSE 'DA LIỄU TỔNG QUÁT'
END;

ALTER TABLE clinic_services ALTER COLUMN specialty_code SET NOT NULL;
CREATE INDEX ix_clinic_services_specialty_active
    ON clinic_services (upper(trim(specialty_code)), display_order)
    WHERE active;
