USE sales_management_system;

-- ===== BASIC QUERIES =====

-- Q1. Retrieve all records from customer_sales
SELECT * FROM customer_sales;

-- Q2. Retrieve all records from branches
SELECT * FROM branches;

-- Q4. Display all sales with status = 'Open'
SELECT * FROM customer_sales WHERE status = 'Open';

-- Q5. Retrieve all sales belonging to the Chennai branch
SELECT s.sale_id, s.`date`, s.name, s.product_name, s.gross_sales, s.received_amount, s.pending_amount
FROM customer_sales s
JOIN branches b ON s.branch_id = b.branch_id
WHERE b.branch_name = 'Chennai';

-- ===== AGGREGATION QUERIES =====

-- Q6. Total gross sales across all branches
SELECT SUM(gross_sales) AS total_gross_sales FROM customer_sales;

-- Q7. Total received amount across all sales
SELECT SUM(received_amount) AS total_received FROM customer_sales;

-- Q8. Total pending amount across all sales
SELECT SUM(pending_amount) AS total_pending FROM customer_sales;

-- Q9. Number of sales per branch
SELECT b.branch_name, COUNT(s.sale_id) AS total_sales
FROM branches b
LEFT JOIN customer_sales s ON b.branch_id = s.branch_id
GROUP BY b.branch_name
ORDER BY total_sales DESC;

-- ===== JOIN-BASED QUERIES =====

-- Q11. Sales details along with branch name
SELECT s.sale_id, s.`date`, s.name, b.branch_name, s.product_name, s.gross_sales
FROM customer_sales s
JOIN branches b ON s.branch_id = b.branch_id
ORDER BY s.sale_id;

-- Q12. Sales details with total payment received (from payment_splits)
SELECT s.sale_id, s.name, s.gross_sales,
       SUM(p.amount_paid) AS total_paid,
       COUNT(p.payment_id) AS number_of_payments
FROM customer_sales s
JOIN payment_splits p ON s.sale_id = p.sale_id
GROUP BY s.sale_id, s.name, s.gross_sales
ORDER BY s.sale_id;

-- Q13. Branch-wise total gross sales
SELECT b.branch_name, SUM(s.gross_sales) AS total_gross_sales
FROM branches b
JOIN customer_sales s ON b.branch_id = s.branch_id
GROUP BY b.branch_name
ORDER BY total_gross_sales DESC;

-- Q15. Sales along with branch admin name
SELECT s.sale_id, s.name, b.branch_name, b.branch_admin_name, s.gross_sales
FROM customer_sales s
JOIN branches b ON s.branch_id = b.branch_id
ORDER BY s.sale_id;

-- ===== FINANCIAL TRACKING QUERIES =====

-- Q16. Sales where pending amount is greater than 5000
SELECT sale_id, name, gross_sales, received_amount, pending_amount
FROM customer_sales
WHERE pending_amount > 5000
ORDER BY pending_amount DESC;

-- Q18. Branch with the highest total gross sales
SELECT b.branch_name, SUM(s.gross_sales) AS total_gross_sales
FROM branches b
JOIN customer_sales s ON b.branch_id = s.branch_id
GROUP BY b.branch_name
ORDER BY total_gross_sales DESC
LIMIT 1;

-- Q20. Payment method-wise total collection
SELECT payment_method,
       COUNT(*) AS number_of_payments,
       SUM(amount_paid) AS total_collected
FROM payment_splits
GROUP BY payment_method
ORDER BY total_collected DESC;