# NUST Barter System - "Barty"

**Barty** is a centralized barter system web application designed specifically for the students and faculty of the National University of Sciences and Technology (NUST). It was created as an end-of-semester project for the Database Systems course.

The platform allows users to trade items (such as books, electronics, clothing, and other goods) without using money. Instead, users can list items they no longer need and specify what they would like to receive in exchange. The system features secure authentication, real-time chat between interested parties, a credibility rating system, and an intuitive user interface.

## 🚀 Features

- **User Authentication**: Secure registration, login, and email verification.
- **Profile Management**: Customize profiles with avatars, departments, and academic years.
- **Product Management**: Upload items with images, descriptions, categories, and desired trades.
- **Real-Time Bidding/Chat**: Integrated live chat (via WebSockets) to negotiate trades.
- **Search and Categories**: Easily filter items by category or search by keywords.
- **Credibility System**: Rate trades and leave reviews to build trust within the community.

---

## 🛠️ Tech Stack

- **Backend**: Python, Flask, Flask-SocketIO
- **Database**: MySQL Server (via Flask-MySQLdb)
- **Frontend**: HTML, CSS, JavaScript (Vanilla), Jinja2 Templates
- **Security**: bcrypt (password hashing), Python-dotenv (environment variables)

---

## ⚙️ Setup Instructions

### 1. Prerequisites

- Python 3.8+
- MySQL Server installed and running

### 2. Clone the Repository

```bash
git clone https://github.com/rayxxee/barty.git
cd barty
```

### 3. Set up the Database

1. Log into your MySQL server.
2. The project includes a complete Database schema. You can run the provided `schema.sql` file or create the database manually:

```sql
CREATE DATABASE nust_barter;
USE nust_barter;
```

3. *(Optional)* If you didn't use the `schema.sql` file, you can copy and run the table creation SQL blocks located in earlier versions of this README or inside the `schema.sql` file itself.

### 4. Configure Environment Variables

1. Copy the example environment file:

   ```bash
   cp .env.example .env
   ```

   *(On Windows Command Prompt, use `copy .env.example .env`)*
2. Open the `.env` file and fill in your secure credentials:
   - `SECRET_KEY`: A random string for secure sessions.
   - `MYSQL_PASSWORD`: Your MySQL root/user password.
   - `EMAIL_ADDRESS`: A Gmail address to send verification emails.
   - `EMAIL_PASSWORD`: An App Password generated from your Google Account settings (not your standard email password).

### 5. Install Dependencies & Run

1. Create and activate a Virtual Environment:

   ```bash
   # Windows
   python -m venv venv
   .\venv\Scripts\activate

   # macOS/Linux
   python3 -m venv venv
   source venv/bin/activate
   ```

2. Install the required Python packages:

   ```bash
   pip install -r requirements.txt
   ```

3. Start the Flask server:

   ```bash
   python app.py
   ```

   *(Note: Because the app uses SocketIO, running via `python app.py` is preferred over `flask run`)*

### 6. Access the Application

Open your web browser and navigate to: **<http://localhost:5000>**

---

## 🔒 Security Notes

- **Never commit your `.env` file**. It is already included in `.gitignore`.
- Ensure email credentials use an App Password if using Gmail, as standard password login via SMTP is blocked by Google.
- The `secret_key` in production should be long, complex, and unguessable.
