-- Run this on the existing insurance_management database AFTER backing it up.
USE insurance_management;

CREATE TABLE IF NOT EXISTS agents (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(150) NOT NULL,
  email VARCHAR(150) UNIQUE,
  phone VARCHAR(30),
  specialization VARCHAR(100),
  commission DECIMAL(10,2) NOT NULL DEFAULT 0,
  status ENUM('Active','Inactive') NOT NULL DEFAULT 'Active',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

ALTER TABLE users
  ADD COLUMN IF NOT EXISTS role ENUM('Admin','Agent','Customer') NOT NULL DEFAULT 'Admin',
  ADD COLUMN IF NOT EXISTS customer_id INT NULL,
  ADD COLUMN IF NOT EXISTS agent_id INT NULL,
  ADD COLUMN IF NOT EXISTS is_active TINYINT(1) NOT NULL DEFAULT 1;

ALTER TABLE customers
  ADD COLUMN IF NOT EXISTS agent_id INT NULL;

-- Optional foreign keys; add only if they do not already exist.
-- MySQL versions that support ADD COLUMN IF NOT EXISTS can run the statements above.
ALTER TABLE users
  ADD INDEX idx_users_customer_id (customer_id),
  ADD INDEX idx_users_agent_id (agent_id);
ALTER TABLE customers
  ADD INDEX idx_customers_agent_id (agent_id);
