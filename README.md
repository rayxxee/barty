# NUST Barter System

A barter system website for students and faculty of NUST University.

## Setup Instructions

1. **Install Python Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set up MySQL Database**
   - Install MySQL if you haven't already
   - Create a new database named `nust_barter`
   - The application will use these default credentials:
     - Host: localhost
     - User: root
     - Password: meowmeow
     - Database: nust_barter

3. **Create Required Tables**
   Run these SQL commands in your MySQL client:
   ```sql
   CREATE TABLE users (
       user_id INT AUTO_INCREMENT PRIMARY KEY,
       username VARCHAR(50) UNIQUE NOT NULL,
       email VARCHAR(100) UNIQUE NOT NULL,
       password_hash VARCHAR(255) NOT NULL,
       user_type ENUM('student', 'faculty'),
       cms_id VARCHAR(20),
       department VARCHAR(100),
       year INT,
       is_verified BOOLEAN DEFAULT FALSE,
       verification_token VARCHAR(255),
       profile_image VARCHAR(255),
       credibility_score FLOAT DEFAULT 0
   );

   CREATE TABLE items (
       item_id INT AUTO_INCREMENT PRIMARY KEY,
       user_id INT NOT NULL,
       title VARCHAR(100) NOT NULL,
       description TEXT NOT NULL,
       category VARCHAR(50) NOT NULL,
       desired_trade TEXT NOT NULL,
       image_url VARCHAR(255),
       status ENUM('available', 'removed') DEFAULT 'available',
       created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
       FOREIGN KEY (user_id) REFERENCES users(user_id)
   );

   CREATE TABLE chats (
       chat_id INT AUTO_INCREMENT PRIMARY KEY,
       sender_id INT NOT NULL,
       receiver_id INT NOT NULL,
       item_id INT NOT NULL,
       message TEXT NOT NULL,
       created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
       FOREIGN KEY (sender_id) REFERENCES users(user_id),
       FOREIGN KEY (receiver_id) REFERENCES users(user_id),
       FOREIGN KEY (item_id) REFERENCES items(item_id)
   );

   CREATE TABLE user_ratings (
       rating_id INT AUTO_INCREMENT PRIMARY KEY,
       transaction_id INT NOT NULL,
       rater_id INT NOT NULL,
       ratee_id INT NOT NULL,
       rating FLOAT NOT NULL,
       comment TEXT,
       created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
       FOREIGN KEY (rater_id) REFERENCES users(user_id),
       FOREIGN KEY (ratee_id) REFERENCES users(user_id)
   );

   CREATE TABLE product_ratings (
       rating_id INT AUTO_INCREMENT PRIMARY KEY,
       transaction_id INT NOT NULL,
       item_id INT NOT NULL,
       user_id INT NOT NULL,
       rating FLOAT NOT NULL,
       comment TEXT,
       created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
       FOREIGN KEY (user_id) REFERENCES users(user_id),
       FOREIGN KEY (item_id) REFERENCES items(item_id)
   );
   ```

4. **Create Upload Directories**
   ```bash
   mkdir -p static/uploads/profile_images
   mkdir -p static/uploads/item_images
   ```

## Running the Application

1. **In VS Code:**
   - Open the project folder in VS Code
   - Open a terminal in VS Code (Terminal > New Terminal)
   - Create and activate a virtual environment:
     ```bash
     python -m venv venv
     # On Windows:
     .\venv\Scripts\activate
     # On macOS/Linux:
     source venv/bin/activate
     ```
   - Install dependencies:
     ```bash
     pip install -r requirements.txt
     ```
   - Run the application:
     ```bash
     flask run
     ```

2. **Access the Application**
   - Open your web browser
   - Go to `http://localhost:5000`

## Features

- User registration and email verification
- Login system
- Profile management
- Item upload and management
- Search functionality
- Real-time chat system
- Rating system for users and products
- Responsive design for mobile and desktop

## Security Notes

- Change the default MySQL password
- Update the email credentials in the .env file
- Keep your secret key secure
- Regularly update dependencies