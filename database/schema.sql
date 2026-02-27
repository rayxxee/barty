CREATE DATABASE IF NOT EXISTS nust_barter;
USE nust_barter;

-- =======================
-- 1. Users Table
-- =======================
CREATE TABLE users (
    user_id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    verification_token VARCHAR(255),
    is_verified BOOLEAN DEFAULT FALSE,
    user_type ENUM('student', 'faculty'),
    cms_id VARCHAR(20),
    department VARCHAR(100),
    year INT,
    profile_image VARCHAR(500),
    credibility_score FLOAT DEFAULT 5.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_email (email),
    INDEX idx_username (username)
);

-- =======================
-- 2. Items Table
-- =======================
CREATE TABLE items (
    item_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    title VARCHAR(100) NOT NULL,
    description TEXT,
    category VARCHAR(50),
    desired_trade VARCHAR(200),
    image_url VARCHAR(500),
    status ENUM('available', 'traded', 'removed') DEFAULT 'available',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    INDEX idx_user_id (user_id)
);

-- =======================
-- 3. Chats Table
-- =======================
CREATE TABLE chats (
    chat_id INT AUTO_INCREMENT PRIMARY KEY,
    sender_id INT,
    receiver_id INT,
    item_id INT,
    message TEXT,
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sender_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (receiver_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (item_id) REFERENCES items(item_id) ON DELETE CASCADE
);

-- =======================
-- 4. Trade Requests Table
-- =======================
CREATE TABLE IF NOT EXISTS trade_requests (
    request_id INT AUTO_INCREMENT PRIMARY KEY,
    sender_id INT,
    receiver_id INT,
    requested_item_id INT,
    offered_item_title VARCHAR(200),
    offered_item_description TEXT,
    offered_item_image VARCHAR(500),
    message TEXT,
    status ENUM('pending', 'accepted', 'declined', 'completed') DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sender_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (receiver_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (requested_item_id) REFERENCES items(item_id) ON DELETE CASCADE
);

-- =======================
-- 5. Trade Completions Table
-- =======================
CREATE TABLE IF NOT EXISTS trade_completions (
    completion_id INT AUTO_INCREMENT PRIMARY KEY,
    request_id INT,
    user_id INT,
    completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (request_id) REFERENCES trade_requests(request_id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    UNIQUE KEY unique_completion (request_id, user_id)
);

-- =======================
-- 6. User Ratings Table
-- =======================
CREATE TABLE user_ratings (
    rating_id INT AUTO_INCREMENT PRIMARY KEY,
    transaction_id INT,
    rater_id INT,
    ratee_id INT,
    rating FLOAT,
    comment TEXT,
    request_id INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (rater_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (ratee_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (request_id) REFERENCES trade_requests(request_id) ON DELETE CASCADE
);

-- =======================
-- 7. Product Ratings Table
-- =======================
CREATE TABLE product_ratings (
    rating_id INT AUTO_INCREMENT PRIMARY KEY,
    transaction_id INT,
    item_id INT,
    user_id INT,
    rating FLOAT,
    comment TEXT,
    request_id INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (item_id) REFERENCES items(item_id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (request_id) REFERENCES trade_requests(request_id) ON DELETE CASCADE
);

-- =======================
-- 8. Transactions Table (Optional - for backward compatibility)
-- =======================
CREATE TABLE transactions (
    transaction_id INT AUTO_INCREMENT PRIMARY KEY,
    item_id INT NOT NULL,
    user_id INT NOT NULL,
    trader_id INT NOT NULL,
    status ENUM('pending', 'completed', 'cancelled') DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (item_id) REFERENCES items(item_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id),
    FOREIGN KEY (trader_id) REFERENCES users(user_id)
);

-- =======================
-- 9. Triggers
-- =======================
DELIMITER //

-- Update user credibility after new rating
CREATE TRIGGER IF NOT EXISTS update_user_credibility_after_rating
AFTER INSERT ON user_ratings
FOR EACH ROW
BEGIN
    UPDATE users
    SET credibility_score = (
        SELECT AVG(rating)
        FROM user_ratings
        WHERE ratee_id = NEW.ratee_id
    )
    WHERE user_id = NEW.ratee_id;
END;//

-- Update user credibility after update
CREATE TRIGGER update_user_credibility_after_update
AFTER UPDATE ON user_ratings
FOR EACH ROW
BEGIN
    UPDATE users
    SET credibility_score = (
        SELECT AVG(rating)
        FROM user_ratings
        WHERE ratee_id = NEW.ratee_id
    )
    WHERE user_id = NEW.ratee_id;
END;//

-- Update user credibility after delete
CREATE TRIGGER update_user_credibility_after_delete
AFTER DELETE ON user_ratings
FOR EACH ROW
BEGIN
    UPDATE users
    SET credibility_score = (
        SELECT AVG(rating)
        FROM user_ratings
        WHERE ratee_id = OLD.ratee_id
    )
    WHERE user_id = OLD.ratee_id;
END;//

-- Prevent trade request to self
CREATE TRIGGER IF NOT EXISTS prevent_self_trade_request
BEFORE INSERT ON trade_requests
FOR EACH ROW
BEGIN
    IF NEW.sender_id = NEW.receiver_id THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Users cannot send trade requests to themselves';
    END IF;
END;//

DELIMITER ;

-- =======================
-- 10. Views
-- =======================
-- Available items view
CREATE OR REPLACE VIEW available_items AS
SELECT 
    i.item_id, i.title, i.description, i.category,
    i.desired_trade, i.image_url, u.username, u.department, u.user_type
FROM items i
JOIN users u ON i.user_id = u.user_id
WHERE i.status = 'available';

-- Pending trade requests view
CREATE OR REPLACE VIEW pending_trade_requests AS
SELECT 
    tr.request_id, tr.offered_item_title, tr.message, tr.created_at,
    u1.username AS sender_name, u2.username AS receiver_name,
    i.title AS requested_item_title
FROM trade_requests tr
JOIN users u1 ON tr.sender_id = u1.user_id
JOIN users u2 ON tr.receiver_id = u2.user_id
JOIN items i ON tr.requested_item_id = i.item_id
WHERE tr.status = 'pending';

-- Completed trades view
CREATE OR REPLACE VIEW completed_trades AS
SELECT 
    tr.request_id, tr.offered_item_title, tr.created_at,
    u1.username AS sender_name, u2.username AS receiver_name,
    i.title AS requested_item_title
FROM trade_requests tr
JOIN users u1 ON tr.sender_id = u1.user_id
JOIN users u2 ON tr.receiver_id = u2.user_id
JOIN items i ON tr.requested_item_id = i.item_id
WHERE tr.status = 'completed';

-- =======================
-- 11. Stored Procedures
-- =======================
DELIMITER //

-- Create trade request
CREATE PROCEDURE create_trade_request(
    IN p_sender_id INT,
    IN p_receiver_id INT,
    IN p_requested_item_id INT,
    IN p_offered_title VARCHAR(200),
    IN p_offered_description TEXT,
    IN p_offered_image VARCHAR(500),
    IN p_message TEXT
)
BEGIN
    INSERT INTO trade_requests 
    (sender_id, receiver_id, requested_item_id, offered_item_title, 
     offered_item_description, offered_item_image, message)
    VALUES (p_sender_id, p_receiver_id, p_requested_item_id, p_offered_title, 
            p_offered_description, p_offered_image, p_message);
END;//

-- Accept trade request
CREATE PROCEDURE accept_trade_request(IN p_request_id INT)
BEGIN
    DECLARE p_item_id INT;
    
    SELECT requested_item_id INTO p_item_id
    FROM trade_requests
    WHERE request_id = p_request_id;
    
    UPDATE trade_requests
    SET status = 'accepted'
    WHERE request_id = p_request_id;
    
    UPDATE items
    SET status = 'traded'
    WHERE item_id = p_item_id;
END;//

-- Complete trade
CREATE PROCEDURE complete_trade(
    IN p_request_id INT,
    IN p_user_id INT
)
BEGIN
    DECLARE completion_count INT;
    
    INSERT IGNORE INTO trade_completions (request_id, user_id)
    VALUES (p_request_id, p_user_id);
    
    SELECT COUNT(*) INTO completion_count
    FROM trade_completions
    WHERE request_id = p_request_id;
    
    IF completion_count >= 2 THEN
        UPDATE trade_requests
        SET status = 'completed'
        WHERE request_id = p_request_id;
    END IF;
END;//

-- Rate trade
CREATE PROCEDURE rate_trade(
    IN p_request_id INT,
    IN p_rater_id INT,
    IN p_ratee_id INT,
    IN p_item_id INT,
    IN p_user_rating FLOAT,
    IN p_product_rating FLOAT,
    IN p_user_comment TEXT,
    IN p_product_comment TEXT
)
BEGIN
    INSERT INTO user_ratings 
    (rater_id, ratee_id, rating, comment, request_id)
    VALUES (p_rater_id, p_ratee_id, p_user_rating, p_user_comment, p_request_id);
    
    INSERT INTO product_ratings 
    (item_id, user_id, rating, comment, request_id)
    VALUES (p_item_id, p_rater_id, p_product_rating, p_product_comment, p_request_id);
END;//

DELIMITER ;

-- Update items table to include 'traded' status if needed
ALTER TABLE items MODIFY COLUMN status ENUM('available', 'traded', 'removed') DEFAULT 'available';

-- Check and add request_id to user_ratings
SET @sql = (
    SELECT IF(
        COUNT(*) = 0,
        'ALTER TABLE user_ratings ADD COLUMN request_id INT NULL',
        'SELECT "Column request_id already exists in user_ratings"'
    )
    FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_SCHEMA = 'nust_barter' 
    AND TABLE_NAME = 'user_ratings' 
    AND COLUMN_NAME = 'request_id'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Add foreign key constraint to user_ratings (only if column was added)
SET @sql = (
    SELECT IF(
        COUNT(*) > 0 AND NOT EXISTS (
            SELECT 1 FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE 
            WHERE TABLE_SCHEMA = 'nust_barter' 
            AND TABLE_NAME = 'user_ratings' 
            AND CONSTRAINT_NAME = 'fk_user_ratings_request'
        ),
        'ALTER TABLE user_ratings ADD CONSTRAINT fk_user_ratings_request FOREIGN KEY (request_id) REFERENCES trade_requests(request_id) ON DELETE CASCADE',
        'SELECT "Foreign key already exists for user_ratings"'
    )
    FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_SCHEMA = 'nust_barter' 
    AND TABLE_NAME = 'user_ratings' 
    AND COLUMN_NAME = 'request_id'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Check and add request_id to product_ratings
SET @sql = (
    SELECT IF(
        COUNT(*) = 0,
        'ALTER TABLE product_ratings ADD COLUMN request_id INT NULL',
        'SELECT "Column request_id already exists in product_ratings"'
    )
    FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_SCHEMA = 'nust_barter' 
    AND TABLE_NAME = 'product_ratings' 
    AND COLUMN_NAME = 'request_id'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Add foreign key constraint to product_ratings (only if column was added)
SET @sql = (
    SELECT IF(
        COUNT(*) > 0 AND NOT EXISTS (
            SELECT 1 FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE 
            WHERE TABLE_SCHEMA = 'nust_barter' 
            AND TABLE_NAME = 'product_ratings' 
            AND CONSTRAINT_NAME = 'fk_product_ratings_request'
        ),
        'ALTER TABLE product_ratings ADD CONSTRAINT fk_product_ratings_request FOREIGN KEY (request_id) REFERENCES trade_requests(request_id) ON DELETE CASCADE',
        'SELECT "Foreign key already exists for product_ratings"'
    )
    FROM INFORMATION_SCHEMA.COLUMNS 
    WHERE TABLE_SCHEMA = 'nust_barter' 
    AND TABLE_NAME = 'product_ratings' 
    AND COLUMN_NAME = 'request_id'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;