USE sales_management_system;

DROP TRIGGER IF EXISTS trg_payment_after_insert;

DELIMITER //

CREATE TRIGGER trg_payment_after_insert
AFTER INSERT ON payment_splits
FOR EACH ROW
BEGIN
    DECLARE total_paid DECIMAL(12,2);

    SELECT COALESCE(SUM(amount_paid), 0) INTO total_paid
    FROM payment_splits
    WHERE sale_id = NEW.sale_id;

    UPDATE customer_sales
    SET received_amount = total_paid,
        status = IF(total_paid >= gross_sales, 'Close', 'Open')
    WHERE sale_id = NEW.sale_id;
END//

DELIMITER ;