CREATE DATABASE IF NOT EXISTS sales_management_system;
USE sales_management_system;

DROP TABLE IF EXISTS payment_splits;
DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS customer_sales;
DROP TABLE IF EXISTS branches;

CREATE TABLE branches (
    branch_id         INT AUTO_INCREMENT PRIMARY KEY,
    branch_name       VARCHAR(100) NOT NULL,
    branch_admin_name VARCHAR(100) NOT NULL
);

CREATE TABLE users (
    user_id   INT AUTO_INCREMENT PRIMARY KEY,
    username  VARCHAR(100) NOT NULL,
    password  VARCHAR(255) NOT NULL,
    branch_id INT NULL,
    role      ENUM('Super Admin', 'Admin') NOT NULL,
    email     VARCHAR(255) NOT NULL UNIQUE,
    CONSTRAINT fk_users_branch
        FOREIGN KEY (branch_id) REFERENCES branches(branch_id)
);

CREATE TABLE customer_sales (
    sale_id         INT AUTO_INCREMENT PRIMARY KEY,
    branch_id       INT NOT NULL,
    `date`          DATE NOT NULL,
    name            VARCHAR(100) NOT NULL,
    mobile_number   VARCHAR(15) NOT NULL,
    product_name    VARCHAR(30) NOT NULL,
    gross_sales     DECIMAL(12,2) NOT NULL,
    received_amount DECIMAL(12,2) NOT NULL DEFAULT 0,
    pending_amount  DECIMAL(12,2) GENERATED ALWAYS AS (gross_sales - received_amount) STORED,
    status          ENUM('Open','Close') NOT NULL DEFAULT 'Open',
    CONSTRAINT fk_sales_branch
        FOREIGN KEY (branch_id) REFERENCES branches(branch_id),
    CONSTRAINT chk_gross    CHECK (gross_sales >= 0),
    CONSTRAINT chk_received CHECK (received_amount >= 0),
    CONSTRAINT uq_sales_mobile UNIQUE (mobile_number),
    INDEX idx_sales_date (`date`)
);

CREATE TABLE payment_splits (
    payment_id     INT AUTO_INCREMENT PRIMARY KEY,
    sale_id        INT NOT NULL,
    payment_date   DATE NOT NULL,
    amount_paid    DECIMAL(12,2) NOT NULL,
    payment_method VARCHAR(50) NOT NULL,
    CONSTRAINT fk_payment_sale
        FOREIGN KEY (sale_id) REFERENCES customer_sales(sale_id) ON DELETE CASCADE,
    CONSTRAINT chk_paid CHECK (amount_paid > 0),
    INDEX idx_payment_sale (sale_id)
);