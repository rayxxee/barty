from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory
from flask_mysqldb import MySQL
import bcrypt
import uuid
import smtplib
from email.mime.text import MIMEText
from datetime import datetime
import MySQLdb
import re
import os
from dotenv import load_dotenv
from werkzeug.utils import secure_filename

# Load environment variables from .env file (with override=True to ensure hot-reloads pick up .env changes)
load_dotenv(override=True)

from flask_socketio import SocketIO, emit, join_room, leave_room

app = Flask(__name__)
socketio = SocketIO(app, 
                   cors_allowed_origins="*", 
                   logger=True, 
                   engineio_logger=True,
                   ping_timeout=60,
                   ping_interval=25)
app.secret_key = os.getenv('SECRET_KEY', 'your-secret-key')

# Configure upload folder
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Create upload folder if it doesn't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Add cache control for static files
@app.after_request
def add_header(response):
    if 'Cache-Control' not in response.headers:
        if request.path.startswith('/static/'):
            # Cache static files for 1 hour
            response.headers['Cache-Control'] = 'public, max-age=3600'
        else:
            # Don't cache dynamic content
            response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    return response

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# MySQL Configuration
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = os.getenv('MYSQL_PASSWORD')
app.config['MYSQL_DB'] = 'nust_barter'
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'
mysql = MySQL(app)

# Initialize database tables
with app.app_context():
    try:
        cur = mysql.connection.cursor()
        cur.close()
        print("Database connection successful")
    except Exception as e:
        print(f"Database connection error: {e}")

# Email Configuration
def get_email_credentials():
    return os.getenv('EMAIL_ADDRESS'), os.getenv('EMAIL_PASSWORD')

def send_verification_email(email, token):
    try:
        msg = MIMEText(f'Click to verify: http://localhost:5000/verify_email/{token}')
        msg['Subject'] = 'Barty - Email Verification'
        email_address, email_password = get_email_credentials()
        msg['From'] = email_address
        msg['To'] = email

        # Updated SMTP configuration
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(email_address, email_password)
            server.send_message(msg)
            print(f"Verification email sent to {email}")
    except smtplib.SMTPAuthenticationError:
        print("SMTP Authentication failed. Please check your email and app password.")
        flash('Failed to send verification email. Please try again later.')
    except Exception as e:
        print(f"Failed to send verification email: {e}")
        flash('Failed to send verification email. Please try again later.')

@app.route('/')
def home():
    # Session protection: redirect to login if user is not authenticated
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    try:
        cur = mysql.connection.cursor()
        # Get all available items grouped by category
        cur.execute("""
            SELECT i.*, u.username, u.department, u.user_type, u.year, u.profile_image 
            FROM items i 
            JOIN users u ON i.user_id = u.user_id 
            WHERE i.status = 'available'
            ORDER BY i.category, i.created_at DESC
        """)
        all_items = cur.fetchall()
        cur.close()
        
        # Group items by category
        items_by_category = {}
        categories = [
            'electronics', 'clothing', 'books', 'home', 'furniture', 
            'toys', 'sports', 'beauty', 'music', 'digital', 'games', 'other'
        ]
        
        # Initialize all categories
        for category in categories:
            items_by_category[category] = []
            
        # Group items
        for item in all_items:
            if item['category'] in items_by_category:
                items_by_category[item['category']].append(item)
        
        return render_template('home.html', items_by_category=items_by_category, categories=categories)
    except Exception as e:
        print(f"Home page error: {e}")
        flash('An error occurred while loading the home page')
        return render_template('home.html', items_by_category={}, categories=[])

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email'].strip()
        password = request.form['password']
        try:
            cur = mysql.connection.cursor()
            cur.execute("SELECT user_id, password_hash, is_verified FROM users WHERE email = %s", (email,))
            user = cur.fetchone()
            cur.close()
            
            if user and bcrypt.checkpw(password.encode('utf-8'), user['password_hash'].encode('utf-8')) and user['is_verified']:
                session['user_id'] = user['user_id']
                return redirect(url_for('home'))
            flash('Invalid credentials or unverified email')
        except Exception as e:
            print(f"Login error: {e}")
            flash('An error occurred during login')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username'].strip()
        email = request.form['email'].strip()
        password = request.form['password']

        # Input validation
        if len(username) > 50:
            flash('Username must be 50 characters or fewer')
            return render_template('register.html')
        if len(email) > 100:
            flash('Email must be 100 characters or fewer')
            return render_template('register.html')
        if len(password) < 8:
            flash('Password must be at least 8 characters')
            return render_template('register.html')
        if not re.match(r'^[a-zA-Z0-9_]+$', username):
            flash('Username can only contain letters, numbers, and underscores')
            return render_template('register.html')
        if not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email):
            flash('Invalid email format')
            return render_template('register.html')

        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        token = str(uuid.uuid4())
        
        cur = mysql.connection.cursor()
        try:
            cur.execute(
                "INSERT INTO users (username, email, password_hash, verification_token) VALUES (%s, %s, %s, %s)",
                (username, email, password_hash, token)
            )
            mysql.connection.commit()
            try:
                send_verification_email(email, token)
                flash('Verification email sent')
                return redirect(url_for('login'))
            except Exception as e:
                mysql.connection.rollback()
                flash('Failed to send verification email')
                print(f"Email error: {e}")
        except MySQLdb.IntegrityError as e:
            if e.args[0] == 1062:
                if 'username' in str(e).lower():
                    flash('Username already exists')
                elif 'email' in str(e).lower():
                    flash('Email already exists')
                else:
                    flash('Username or email already exists')
            else:
                flash('Registration failed due to a database error')
                print(f"Database error: {e}")
        except MySQLdb.ProgrammingError as e:
            if e.args[0] == 1146:
                flash('Database table missing. Please contact support.')
                print(f"Table error: {e}")
            else:
                flash('Registration failed due to a database error')
                print(f"Programming error: {e}")
        except MySQLdb.OperationalError as e:
            flash('Database connection error')
            print(f"Operational error: {e}")
        except Exception as e:
            flash('An unexpected error occurred during registration')
            print(f"Unexpected error: {e}")
        finally:
            cur.close()
    return render_template('register.html')

@app.route('/verify_email/<token>')
def verify_email(token):
    try:
        cur = mysql.connection.cursor()
        cur.execute("UPDATE users SET is_verified = TRUE, verification_token = NULL WHERE verification_token = %s", (token,))
        mysql.connection.commit()
        cur.close()
        flash('Email verified! Please complete your profile')
        return redirect(url_for('profile_setup'))
    except Exception as e:
        print(f"Verify email error: {e}")
        flash('An error occurred during email verification')
        return redirect(url_for('login'))

@app.route('/profile_setup', methods=['GET', 'POST'])
def profile_setup():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        user_type = request.form['user_type']
        cms_id = request.form.get('cms_id', '').strip()
        department = request.form['department'].strip()
        year = request.form.get('year', None)
        
        if len(cms_id) > 20:
            flash('CMS ID must be 20 characters or fewer')
            return render_template('profile_setup.html')
        if len(department) > 100:
            flash('Department must be 100 characters or fewer')
            return render_template('profile_setup.html')
        if user_type not in ['student', 'faculty']:
            flash('Invalid user type')
            return render_template('profile_setup.html')
        
        try:
            cur = mysql.connection.cursor()
            cur.execute(
                "UPDATE users SET user_type = %s, cms_id = %s, department = %s, year = %s WHERE user_id = %s",
                (user_type, cms_id, department, year, session['user_id'])
            )
            mysql.connection.commit()
            cur.close()
            return redirect(url_for('home'))
        except Exception as e:
            print(f"Profile setup error: {e}")
            flash('An error occurred while updating profile')
    return render_template('profile_setup.html')

@app.route('/search', methods=['GET'])
def search():
    return render_template('search.html')

@app.route('/search_results', methods=['GET'])
def search_results():
    query = request.args.get('query', '').strip()
    category = request.args.get('category', '').strip()
    try:
        cur = mysql.connection.cursor()
        if category:
            cur.execute("""
                SELECT i.*, u.username, u.department, u.user_type, u.year, u.profile_image 
                FROM items i 
                JOIN users u ON i.user_id = u.user_id 
                WHERE i.title LIKE %s AND i.category = %s AND i.status = 'available'
            """, (f'%{query}%', category))
        else:
            cur.execute("""
                SELECT i.*, u.username, u.department, u.user_type, u.year, u.profile_image 
                FROM items i 
                JOIN users u ON i.user_id = u.user_id 
                WHERE i.title LIKE %s AND i.status = 'available'
            """, (f'%{query}%',))
        items = cur.fetchall()
        cur.close()
        return render_template('search_results.html', items=items)
    except Exception as e:
        print(f"Search error: {e}")
        flash('An error occurred during search')
        return render_template('search_results.html', items=[])

@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    try:
        cur = mysql.connection.cursor()
        # Get user information
        cur.execute("SELECT * FROM users WHERE user_id = %s", (session['user_id'],))
        user = cur.fetchone()
        
        if not user:
            flash('User not found')
            return redirect(url_for('logout'))
            
        # Get user's active items
        cur.execute("""
            SELECT i.*, u.username, u.department, u.user_type, u.year 
            FROM items i 
            JOIN users u ON i.user_id = u.user_id 
            WHERE i.user_id = %s AND i.status = 'available'
            ORDER BY i.created_at DESC
        """, (session['user_id'],))
        user_items = cur.fetchall()
        
        # Get user's completed trades (both sent and received)
        cur.execute("""
            SELECT tr.*, i.title as item_title, i.image_url as item_image,
                   CASE 
                       WHEN tr.sender_id = %s THEN 'sent'
                       ELSE 'received'
                   END as trade_type,
                   CASE 
                       WHEN tr.sender_id = %s THEN u2.username
                       ELSE u1.username
                   END as other_user_name
            FROM trade_requests tr
            JOIN items i ON tr.requested_item_id = i.item_id
            JOIN users u1 ON tr.sender_id = u1.user_id
            JOIN users u2 ON tr.receiver_id = u2.user_id
            WHERE (tr.sender_id = %s OR tr.receiver_id = %s) 
            AND tr.status = 'completed'
            ORDER BY tr.created_at DESC
        """, (session['user_id'], session['user_id'], session['user_id'], session['user_id']))
        completed_trades = cur.fetchall()
        
        # Get user ratings (ratings received by this user)
        cur.execute("""
            SELECT ur.*, u.username as rater_username, u.profile_image as rater_image
            FROM user_ratings ur
            JOIN users u ON ur.rater_id = u.user_id
            WHERE ur.ratee_id = %s
            ORDER BY ur.created_at DESC
            LIMIT 10
        """, (session['user_id'],))
        user_ratings = cur.fetchall()
        
        cur.close()
        return render_template('profile.html', 
                             user=user, 
                             user_items=user_items,
                             completed_trades=completed_trades,
                             user_ratings=user_ratings)
    except Exception as e:
        print(f"Profile error: {e}")
        flash('An error occurred while loading profile')
        return redirect(url_for('home'))

@app.route('/user/<int:user_id>')
def user_profile(user_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    try:
        cur = mysql.connection.cursor()
        # Get user information
        cur.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
        user = cur.fetchone()
        
        if not user:
            flash('User not found')
            return redirect(url_for('home'))
            
        # Get user's active items
        cur.execute("""
            SELECT i.*, u.username, u.department, u.user_type, u.year 
            FROM items i 
            JOIN users u ON i.user_id = u.user_id 
            WHERE i.user_id = %s AND i.status = 'available'
            ORDER BY i.created_at DESC
        """, (user_id,))
        user_items = cur.fetchall()
        
        # Get user's completed trades (only show public info)
        cur.execute("""
            SELECT tr.*, i.title as item_title,
                   CASE 
                       WHEN tr.sender_id = %s THEN 'sent'
                       ELSE 'received'
                   END as trade_type
            FROM trade_requests tr
            JOIN items i ON tr.requested_item_id = i.item_id
            WHERE (tr.sender_id = %s OR tr.receiver_id = %s) 
            AND tr.status = 'completed'
            ORDER BY tr.created_at DESC
            LIMIT 5
        """, (user_id, user_id, user_id))
        completed_trades = cur.fetchall()
        
        # Get user ratings (ratings received by this user)
        cur.execute("""
            SELECT ur.*, u.username as rater_username, u.profile_image as rater_image
            FROM user_ratings ur
            JOIN users u ON ur.rater_id = u.user_id
            WHERE ur.ratee_id = %s
            ORDER BY ur.created_at DESC
            LIMIT 10
        """, (user_id,))
        user_ratings = cur.fetchall()
        
        cur.close()
        return render_template('profile.html', 
                             user=user, 
                             user_items=user_items,
                             completed_trades=completed_trades,
                             user_ratings=user_ratings)
    except Exception as e:
        print(f"Profile error: {e}")
        flash('An error occurred while loading profile')
        return redirect(url_for('home'))

@app.route('/product/<int:item_id>')
def product_view(item_id):
    try:
        cur = mysql.connection.cursor()
        # Get item with seller information
        cur.execute("""
            SELECT i.*, u.username, u.department, u.user_type, u.year, u.profile_image 
            FROM items i 
            JOIN users u ON i.user_id = u.user_id 
            WHERE i.item_id = %s
        """, (item_id,))
        item = cur.fetchone()
        cur.close()
        if item:
            return render_template('product_view.html', item=item)
        flash('Item not found')
        return redirect(url_for('home'))
    except Exception as e:
        print(f"Product view error: {e}")
        flash('An error occurred while loading item')
        return redirect(url_for('home'))

@socketio.on('connect')
def handle_connect():
    print(f"Client connected: {request.sid}")
    if 'user_id' not in session:
        print("No user_id in session, disconnecting client")
        return False
    return True

@socketio.on('disconnect')
def handle_disconnect():
    print(f"Client disconnected: {request.sid}")

@socketio.on('join')
def on_join(data):
    if 'user_id' not in session:
        print("No user_id in session for join")
        return
    
    room = data['room']
    join_room(room)
    print(f"Client {request.sid} joined room: {room}")
    
    # Get username for status message
    cur = mysql.connection.cursor()
    cur.execute("SELECT username FROM users WHERE user_id = %s", (session['user_id'],))
    user = cur.fetchone()
    cur.close()
    
    username = user['username'] if user else 'Someone'
    emit('status', {'msg': f"{username} has joined the chat."}, room=room)

@socketio.on('leave')
def on_leave(data):
    if 'user_id' not in session:
        return
    
    room = data['room']
    leave_room(room)
    print(f"Client {request.sid} left room: {room}")
    
    # Get username for status message
    cur = mysql.connection.cursor()
    cur.execute("SELECT username FROM users WHERE user_id = %s", (session['user_id'],))
    user = cur.fetchone()
    cur.close()
    
    username = user['username'] if user else 'Someone'
    emit('status', {'msg': f"{username} has left the chat."}, room=room)

@socketio.on('send_message')
def handle_message(data):
    if 'user_id' not in session:
        print("No user_id in session for message")
        emit('error', {'msg': 'You must be logged in to send messages'})
        return
    
    print(f"Received message data: {data}")
    room = data['room']
    message = data['message']
    sender_id = session['user_id']
    receiver_id = data['receiver_id']
    item_id = data.get('item_id')
    
    if not all([room, message, receiver_id, item_id]):
        print("Missing required message data")
        emit('error', {'msg': 'Missing required message data'})
        return
    
    try:
        cur = mysql.connection.cursor()
        
        # Verify the item exists and is available
        cur.execute("SELECT status FROM items WHERE item_id = %s", (item_id,))
        item = cur.fetchone()
        if not item or item['status'] != 'available':
            emit('error', {'msg': 'This item is no longer available'})
            return
        
        # Insert the message
        cur.execute("""
            INSERT INTO chats (sender_id, receiver_id, item_id, message, sent_at)
            VALUES (%s, %s, %s, %s, NOW())
        """, (sender_id, receiver_id, item_id, message))
        mysql.connection.commit()
        
        # Get sender's info
        cur.execute("SELECT username, profile_image FROM users WHERE user_id = %s", (sender_id,))
        sender = cur.fetchone()
        sender_username = sender['username'] if sender else 'Unknown'
        profile_image = sender['profile_image'] if sender else None
        
        cur.close()
        
        print(f"Emitting message to room {room}")
        # Emit the message to the room
        emit('new_message', {
            'message': message,
            'sender': sender_username,
            'sender_id': sender_id,
            'profile_image': profile_image,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }, room=room)
        
    except Exception as e:
        print(f"Error sending message: {e}")
        emit('error', {'msg': 'Failed to send message'})

@app.route('/chat/<int:user_id>/<int:item_id>')
def chat(user_id, item_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    try:
        cur = mysql.connection.cursor()
        # Get receiver's info
        cur.execute("SELECT username, profile_image, user_id FROM users WHERE user_id = %s", (user_id,))
        receiver = cur.fetchone()
        
        if not receiver:
            flash('User not found')
            return redirect(url_for('home'))
        
        # Get chat history
        cur.execute("""
            SELECT c.*, u.username, u.profile_image, i.title as item_title
            FROM chats c
            JOIN users u ON c.sender_id = u.user_id 
            JOIN items i ON c.item_id = i.item_id
            WHERE ((c.sender_id = %s AND c.receiver_id = %s) 
            OR (c.sender_id = %s AND c.receiver_id = %s))
            AND c.item_id = %s
            ORDER BY c.sent_at ASC
        """, (session['user_id'], user_id, user_id, session['user_id'], item_id))
        messages = cur.fetchall()
        
        # Verify item exists
        cur.execute("SELECT title FROM items WHERE item_id = %s AND status = 'available'", (item_id,))
        item = cur.fetchone()
        if not item:
            flash('Item not found or unavailable')
            return redirect(url_for('home'))
        
        cur.close()
        
        # Create a unique room ID for this chat
        room = f"chat_{min(session['user_id'], user_id)}_{max(session['user_id'], user_id)}_{item_id}"
        
        return render_template('chat.html', 
                            receiver=receiver, 
                            messages=messages, 
                            room=room,
                            item_id=item_id)
    except Exception as e:
        print(f"Chat error: {e}")
        flash('An error occurred while loading the chat')
        return redirect(url_for('home'))

@app.route('/upload', methods=['GET', 'POST'])
def product_upload():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        title = request.form['title'].strip()
        description = request.form['description'].strip()
        category = request.form['category'].strip()
        desired_trade = request.form['desired_trade'].strip()
        
        if len(title) > 100:
            flash('Title must be 100 characters or fewer')
            return render_template('product_upload.html')
        if len(category) > 50:
            flash('Category must be 50 characters or fewer')
            return render_template('product_upload.html')

        # Require image
        if 'image' not in request.files or not request.files['image'] or not request.files['image'].filename:
            flash('You must upload an image for your item.')
            return render_template('product_upload.html')
        
        try:
            cur = mysql.connection.cursor()
            
            # Handle image upload
            image_url = None
            if 'image' in request.files:
                file = request.files['image']
                if file and file.filename and allowed_file(file.filename):
                    # Create a unique filename using timestamp
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    filename = secure_filename(f"item_{timestamp}_{file.filename}")
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    
                    # Save the file
                    file.save(filepath)
                    
                    # Set image URL
                    image_url = url_for('static', filename=f'uploads/{filename}')
            
            # Insert item with image URL
            cur.execute(
                "INSERT INTO items (user_id, title, description, category, desired_trade, image_url) VALUES (%s, %s, %s, %s, %s, %s)",
                (session['user_id'], title, description, category, desired_trade, image_url)
            )
            mysql.connection.commit()
            cur.close()
            flash('Item uploaded successfully')
            return redirect(url_for('home'))
        except Exception as e:
            print(f"Upload error: {e}")
            flash('An error occurred while uploading item')
    return render_template('product_upload.html')

@app.route('/remove_item/<int:item_id>', methods=['POST'])
def remove_item(item_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    try:
        cur = mysql.connection.cursor()
        # First check if the item exists and belongs to the user
        cur.execute(
            "SELECT * FROM items WHERE item_id = %s AND user_id = %s",
            (item_id, session['user_id'])
        )
        item = cur.fetchone()
        
        if not item:
            flash('Item not found or you do not have permission to remove it')
            return redirect(url_for('profile'))
            
        # Update the item status to removed
        cur.execute(
            "UPDATE items SET status = 'removed' WHERE item_id = %s AND user_id = %s",
            (item_id, session['user_id'])
        )
        mysql.connection.commit()
        cur.close()
        flash('Item removed successfully')
        return redirect(url_for('profile'))
    except Exception as e:
        print(f"Remove item error: {e}")
        flash('An error occurred while removing item')
        return redirect(url_for('profile'))

@app.route('/rate/<int:transaction_id>', methods=['POST'])
def rate(transaction_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    try:
        user_rating = float(request.form['user_rating'])
        product_rating = float(request.form['product_rating'])
        user_comment = request.form['user_comment'].strip()
        product_comment = request.form['product_comment'].strip()
        ratee_id = int(request.form['ratee_id'])
        item_id = int(request.form['item_id'])
        
        if not (1 <= user_rating <= 5 and 1 <= product_rating <= 5):
            flash('Ratings must be between 1 and 5')
            return redirect(url_for('profile'))
        
        cur = mysql.connection.cursor()
        cur.execute(
            "INSERT INTO user_ratings (transaction_id, rater_id, ratee_id, rating, comment) VALUES (%s, %s, %s, %s, %s)",
            (transaction_id, session['user_id'], ratee_id, user_rating, user_comment)
        )
        cur.execute(
            "INSERT INTO product_ratings (transaction_id, item_id, user_id, rating, comment) VALUES (%s, %s, %s, %s, %s)",
            (transaction_id, item_id, session['user_id'], product_rating, product_comment)
        )
        cur.execute(
            "UPDATE users SET credibility_score = (SELECT AVG(rating) FROM user_ratings WHERE ratee_id = %s) WHERE user_id = %s",
            (ratee_id, ratee_id)
        )
        mysql.connection.commit()
        cur.close()
        flash('Rating submitted')
        return redirect(url_for('profile'))
    except Exception as e:
        print(f"Rating error: {e}")
        flash('An error occurred while submitting rating')
        return redirect(url_for('profile'))

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    try:
        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM users WHERE user_id = %s", (session['user_id'],))
        user = cur.fetchone()
        cur.close()
        
        if not user:
            flash('User not found')
            return redirect(url_for('logout'))
            
        if request.method == 'POST':
            department = request.form['department'].strip()
            year = request.form.get('year', None)
            
            if len(department) > 100:
                flash('Department must be 100 characters or fewer')
                return render_template('settings.html', user=user)
            
            try:
                cur = mysql.connection.cursor()
                
                # Handle profile image upload
                if 'profile_image' in request.files:
                    file = request.files['profile_image']
                    if file and file.filename and allowed_file(file.filename):
                        # Create a unique filename using user_id and timestamp
                        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                        filename = secure_filename(f"{session['user_id']}_{timestamp}_{file.filename}")
                        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                        
                        # Save the file
                        file.save(filepath)
                        
                        # Update profile image path in database
                        image_url = url_for('static', filename=f'uploads/{filename}')
                        cur.execute(
                            "UPDATE users SET profile_image = %s WHERE user_id = %s",
                            (image_url, session['user_id'])
                        )
                
                # Update other profile information
                cur.execute(
                    "UPDATE users SET department = %s, year = %s WHERE user_id = %s",
                    (department, year, session['user_id'])
                )
                mysql.connection.commit()
                cur.close()
                flash('Profile updated')
                return redirect(url_for('profile'))
            except Exception as e:
                print(f"Settings error: {e}")
                flash('An error occurred while updating settings')
        
        return render_template('settings.html', user=user)
    except Exception as e:
        print(f"Settings error: {e}")
        flash('An error occurred while loading settings')
        return redirect(url_for('home'))

@app.route('/change_password', methods=['POST'])
def change_password():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    current_password = request.form['current_password']
    new_password = request.form['new_password']
    confirm_password = request.form['confirm_password']
    
    if new_password != confirm_password:
        flash('New passwords do not match')
        return redirect(url_for('settings'))
    
    if len(new_password) < 8:
        flash('New password must be at least 8 characters long')
        return redirect(url_for('settings'))
    
    try:
        cur = mysql.connection.cursor()
        # Get current password hash
        cur.execute("SELECT password_hash FROM users WHERE user_id = %s", (session['user_id'],))
        user = cur.fetchone()
        
        if not user or not bcrypt.checkpw(current_password.encode('utf-8'), user['password_hash'].encode('utf-8')):
            flash('Current password is incorrect')
            return redirect(url_for('settings'))
        
        # Hash and update new password
        new_password_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        cur.execute(
            "UPDATE users SET password_hash = %s WHERE user_id = %s",
            (new_password_hash, session['user_id'])
        )
        mysql.connection.commit()
        cur.close()
        
        flash('Password updated successfully')
        return redirect(url_for('settings'))
    except Exception as e:
        print(f"Password change error: {e}")
        flash('An error occurred while changing password')
        return redirect(url_for('settings'))

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login'))

@app.route('/chats')
def chat_inbox():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    try:
        cur = mysql.connection.cursor()
        # Get all unique chat conversations for the user
        query = """
            WITH LastMessages AS (
                SELECT 
                    item_id,
                    MAX(sent_at) as last_time
                FROM chats
                WHERE sender_id = %s OR receiver_id = %s
                GROUP BY item_id
            )
            SELECT 
                c.item_id,
                i.title as item_title,
                CASE 
                    WHEN c.sender_id = %s THEN c.receiver_id
                    ELSE c.sender_id
                END as other_user_id,
                CASE 
                    WHEN c.sender_id = %s THEN u2.username
                    ELSE u1.username
                END as other_username,
                CASE 
                    WHEN c.sender_id = %s THEN u2.department
                    ELSE u1.department
                END as other_department,
                CASE 
                    WHEN c.sender_id = %s THEN u2.user_type
                    ELSE u1.user_type
                END as other_user_type,
                CASE 
                    WHEN c.sender_id = %s THEN u2.profile_image
                    ELSE u1.profile_image
                END as other_user_image,
                (
                    SELECT message 
                    FROM chats 
                    WHERE item_id = c.item_id 
                    AND sent_at = lm.last_time
                    LIMIT 1
                ) as last_message,
                lm.last_time as last_message_time,
                (
                    SELECT COUNT(*) 
                    FROM chats 
                    WHERE item_id = c.item_id 
                    AND receiver_id = %s 
                    AND sender_id != %s
                    AND sent_at > (
                        SELECT COALESCE(MAX(sent_at), '1970-01-01')
                        FROM chats 
                        WHERE item_id = c.item_id 
                        AND sender_id = %s
                    )
                ) as unread_count
            FROM chats c
            JOIN items i ON c.item_id = i.item_id
            JOIN users u1 ON c.sender_id = u1.user_id
            JOIN users u2 ON c.receiver_id = u2.user_id
            JOIN LastMessages lm ON c.item_id = lm.item_id
            WHERE c.sender_id = %s OR c.receiver_id = %s
            GROUP BY c.item_id, i.title, other_user_id, other_username, 
                     other_department, other_user_type, other_user_image, lm.last_time
            ORDER BY lm.last_time DESC
        """
        params = (session['user_id'], session['user_id'],  # LastMessages CTE
                 session['user_id'], session['user_id'],  # CASE statements
                 session['user_id'], session['user_id'],  # More CASE statements
                 session['user_id'],                      # Profile image CASE
                 session['user_id'], session['user_id'],  # Unread count subquery
                 session['user_id'],                      # Last unread count parameter
                 session['user_id'], session['user_id'])  # Main query WHERE clause
        
        print("Executing query with params:", params)  # Debug print
        cur.execute(query, params)
        conversations = cur.fetchall()
        
        # Format timestamps
        for conv in conversations:
            if conv['last_message_time']:
                conv['formatted_time'] = conv['last_message_time'].strftime('%d-%m-%Y %H:%M')
            else:
                conv['formatted_time'] = 'No messages'
        
        cur.close()
        return render_template('chat_inbox.html', conversations=conversations)
    except Exception as e:
        print(f"Chat inbox error details: {str(e)}")  # More detailed error logging
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")  # Print full traceback
        flash('An error occurred while loading chat inbox')
        return render_template('chat_inbox.html', conversations=[])

@app.route('/initiate_trade/<int:item_id>', methods=['GET', 'POST'])
def initiate_trade(item_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        # Handle trade request submission
        offered_title = request.form['offered_title'].strip()
        offered_description = request.form['offered_description'].strip()
        message = request.form['message'].strip()
        
        # Validation
        if not offered_title or not offered_description:
            flash('Please provide title and description for your offered item')
            return redirect(url_for('initiate_trade', item_id=item_id))
        
        try:
            cur = mysql.connection.cursor()
            
            # Get the item owner
            cur.execute("SELECT user_id FROM items WHERE item_id = %s", (item_id,))
            item = cur.fetchone()
            
            if not item:
                flash('Item not found')
                return redirect(url_for('home'))
            
            if item['user_id'] == session['user_id']:
                flash('You cannot trade with yourself')
                return redirect(url_for('product_view', item_id=item_id))
            
            # Handle image upload
            image_url = None
            if 'offered_image' in request.files and request.files['offered_image'].filename:
                file = request.files['offered_image']
                if file and allowed_file(file.filename):
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    filename = secure_filename(f"trade_{timestamp}_{file.filename}")
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    file.save(filepath)
                    image_url = url_for('static', filename=f'uploads/{filename}')
            
            # Create trade request
            cur.execute('''
                INSERT INTO trade_requests 
                (sender_id, receiver_id, requested_item_id, offered_item_title, 
                 offered_item_description, offered_item_image, message)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            ''', (session['user_id'], item['user_id'], item_id, offered_title, 
                  offered_description, image_url, message))
            
            mysql.connection.commit()
            cur.close()
            
            flash('Trade request sent successfully!')
            return redirect(url_for('product_view', item_id=item_id))
            
        except Exception as e:
            print(f"Error creating trade request: {e}")
            flash('An error occurred while sending the trade request')
            return redirect(url_for('product_view', item_id=item_id))
    
    # GET request - show trade form
    try:
        cur = mysql.connection.cursor()
        cur.execute('''
            SELECT i.*, u.username 
            FROM items i 
            JOIN users u ON i.user_id = u.user_id 
            WHERE i.item_id = %s
        ''', (item_id,))
        item = cur.fetchone()
        cur.close()
        
        if not item:
            flash('Item not found')
            return redirect(url_for('home'))
        
        return render_template('initiate_trade.html', item=item)
        
    except Exception as e:
        print(f"Error loading trade form: {e}")
        flash('An error occurred')
        return redirect(url_for('home'))

@app.route('/trade_requests')
def trade_requests():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    try:
        cur = mysql.connection.cursor()
        
        # Get incoming trade requests (all statuses except declined)
        cur.execute('''
            SELECT tr.*, i.title as requested_item_title, i.image_url as requested_item_image,
                   u.username as sender_username, u.profile_image as sender_image
            FROM trade_requests tr
            JOIN items i ON tr.requested_item_id = i.item_id
            JOIN users u ON tr.sender_id = u.user_id
            WHERE tr.receiver_id = %s AND tr.status != 'declined'
            ORDER BY 
                CASE tr.status 
                    WHEN 'pending' THEN 1
                    WHEN 'accepted' THEN 2
                    WHEN 'completed' THEN 3
                    ELSE 4
                END,
                tr.created_at DESC
        ''', (session['user_id'],))
        incoming_requests = cur.fetchall()
        
        # Get outgoing trade requests (all statuses)
        cur.execute('''
            SELECT tr.*, i.title as requested_item_title, i.image_url as requested_item_image,
                   u.username as receiver_username, u.profile_image as receiver_image
            FROM trade_requests tr
            JOIN items i ON tr.requested_item_id = i.item_id
            JOIN users u ON tr.receiver_id = u.user_id
            WHERE tr.sender_id = %s
            ORDER BY 
                CASE tr.status 
                    WHEN 'pending' THEN 1
                    WHEN 'accepted' THEN 2
                    WHEN 'completed' THEN 3
                    WHEN 'declined' THEN 4
                    ELSE 5
                END,
                tr.created_at DESC
        ''', (session['user_id'],))
        outgoing_requests = cur.fetchall()
        
        cur.close()
        return render_template('trade_requests.html', 
                             incoming_requests=incoming_requests,
                             outgoing_requests=outgoing_requests)
        
    except Exception as e:
        print(f"Error loading trade requests: {e}")
        flash('An error occurred while loading trade requests')
        return render_template('trade_requests.html', incoming_requests=[], outgoing_requests=[])

@app.route('/respond_trade/<int:request_id>/<action>')
def respond_trade(request_id, action):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if action not in ['accept', 'decline']:
        flash('Invalid action')
        return redirect(url_for('trade_requests'))
    
    try:
        cur = mysql.connection.cursor()
        
        # Verify this is the receiver's request
        cur.execute('''
            SELECT * FROM trade_requests 
            WHERE request_id = %s AND receiver_id = %s AND status = 'pending'
        ''', (request_id, session['user_id']))
        
        trade_request = cur.fetchone()
        if not trade_request:
            flash('Trade request not found or unauthorized')
            return redirect(url_for('trade_requests'))
        
        # Update status
        new_status = 'accepted' if action == 'accept' else 'declined'
        cur.execute('''
            UPDATE trade_requests 
            SET status = %s 
            WHERE request_id = %s
        ''', (new_status, request_id))
        
        # If accepted, mark the item as traded
        if action == 'accept':
            cur.execute('''
                UPDATE items 
                SET status = 'traded' 
                WHERE item_id = %s
            ''', (trade_request['requested_item_id'],))
        
        mysql.connection.commit()
        cur.close()
        
        flash(f'Trade request {action}ed successfully!')
        return redirect(url_for('trade_requests'))
        
    except Exception as e:
        print(f"Error responding to trade: {e}")
        flash('An error occurred while responding to the trade request')
        return redirect(url_for('trade_requests'))

@app.route('/complete_trade/<int:request_id>')
def complete_trade(request_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    try:
        cur = mysql.connection.cursor()
        
        # Verify user is part of this trade
        cur.execute('''
            SELECT * FROM trade_requests 
            WHERE request_id = %s AND status = 'accepted'
            AND (sender_id = %s OR receiver_id = %s)
        ''', (request_id, session['user_id'], session['user_id']))
        
        trade_request = cur.fetchone()
        if not trade_request:
            flash('Trade request not found or unauthorized')
            return redirect(url_for('trade_requests'))
        
        # Record completion
        cur.execute('''
            INSERT IGNORE INTO trade_completions (request_id, user_id)
            VALUES (%s, %s)
        ''', (request_id, session['user_id']))
        
        # Check if both parties have completed
        cur.execute('''
            SELECT COUNT(*) as count 
            FROM trade_completions 
            WHERE request_id = %s
        ''', (request_id,))
        
        completion_count = cur.fetchone()['count']
        
        # If both completed, mark trade as completed
        if completion_count >= 2:
            cur.execute('''
                UPDATE trade_requests 
                SET status = 'completed' 
                WHERE request_id = %s
            ''', (request_id,))
        
        mysql.connection.commit()
        cur.close()
        
        if completion_count >= 2:
            flash('Trade completed successfully! You can now rate each other.')
        else:
            flash('Trade completion recorded. Waiting for the other party to confirm.')
        
        return redirect(url_for('trade_requests'))
        
    except Exception as e:
        print(f"Error completing trade: {e}")
        flash('An error occurred while completing the trade')
        return redirect(url_for('trade_requests'))

@app.route('/rate_trade/<int:request_id>', methods=['GET', 'POST'])
def rate_trade(request_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        user_rating = float(request.form['user_rating'])
        product_rating = float(request.form['product_rating'])
        user_comment = request.form['user_comment'].strip()
        product_comment = request.form['product_comment'].strip()
        
        if not (1 <= user_rating <= 5 and 1 <= product_rating <= 5):
            flash('Ratings must be between 1 and 5')
            return redirect(url_for('rate_trade', request_id=request_id))
        
        try:
            cur = mysql.connection.cursor()
            
            # Get trade details
            cur.execute('''
                SELECT * FROM trade_requests 
                WHERE request_id = %s AND status = 'completed'
                AND (sender_id = %s OR receiver_id = %s)
            ''', (request_id, session['user_id'], session['user_id']))
            
            trade = cur.fetchone()
            if not trade:
                flash('Trade not found or not completed')
                return redirect(url_for('trade_requests'))
            
            # Determine who to rate
            if trade['sender_id'] == session['user_id']:
                ratee_id = trade['receiver_id']
                item_id = trade['requested_item_id']
            else:
                ratee_id = trade['sender_id']
                item_id = trade['requested_item_id']
            
            # Insert user rating
            cur.execute('''
                INSERT INTO user_ratings 
                (rater_id, ratee_id, rating, comment, request_id)
                VALUES (%s, %s, %s, %s, %s)
            ''', (session['user_id'], ratee_id, user_rating, user_comment, request_id))
            
            # Insert product rating
            cur.execute('''
                INSERT INTO product_ratings 
                (item_id, user_id, rating, comment, request_id)
                VALUES (%s, %s, %s, %s, %s)
            ''', (item_id, session['user_id'], product_rating, product_comment, request_id))
            
            # Update user credibility
            cur.execute('''
                UPDATE users 
                SET credibility_score = (
                    SELECT AVG(rating) 
                    FROM user_ratings 
                    WHERE ratee_id = %s
                ) 
                WHERE user_id = %s
            ''', (ratee_id, ratee_id))
            
            mysql.connection.commit()
            cur.close()
            
            flash('Ratings submitted successfully!')
            return redirect(url_for('trade_requests'))
            
        except Exception as e:
            print(f"Error submitting ratings: {e}")
            flash('An error occurred while submitting ratings')
            return redirect(url_for('rate_trade', request_id=request_id))
    
    # GET request - show rating form
    try:
        cur = mysql.connection.cursor()
        
        # Get trade details with user and item info
        cur.execute('''
            SELECT tr.*, i.title as item_title,
                   u1.username as sender_name, u2.username as receiver_name
            FROM trade_requests tr
            JOIN items i ON tr.requested_item_id = i.item_id
            JOIN users u1 ON tr.sender_id = u1.user_id
            JOIN users u2 ON tr.receiver_id = u2.user_id
            WHERE tr.request_id = %s AND tr.status = 'completed'
            AND (tr.sender_id = %s OR tr.receiver_id = %s)
        ''', (request_id, session['user_id'], session['user_id']))
        
        trade = cur.fetchone()
        if not trade:
            flash('Trade not found or not completed')
            return redirect(url_for('trade_requests'))
        
        # Check if already rated
        cur.execute('''
            SELECT COUNT(*) as count 
            FROM user_ratings 
            WHERE rater_id = %s AND request_id = %s
        ''', (session['user_id'], request_id))
        
        already_rated = cur.fetchone()['count'] > 0
        
        cur.close()
        return render_template('rate_trade.html', trade=trade, already_rated=already_rated)
        
    except Exception as e:
        print(f"Error loading rating form: {e}")
        flash('An error occurred')
        return redirect(url_for('trade_requests'))

@app.route('/product/<int:item_id>/trade_requests')
def product_trade_requests(item_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    try:
        cur = mysql.connection.cursor()
        
        # Debug: Print the item_id being queried
        print(f"Querying for item_id: {item_id}")
        
        # Verify user owns this item - include item_id in the result
        cur.execute("SELECT user_id, title, item_id FROM items WHERE item_id = %s", (item_id,))
        item = cur.fetchone()
        
        print(f"Query result: {item}")  # Debug print
        print(f"Session user_id: {session.get('user_id')}")  # Debug print
        
        if not item:
            flash('Item not found')
            return redirect(url_for('home'))
        
        if item['user_id'] != session['user_id']:
            flash('You are not authorized to view trade requests for this item')
            return redirect(url_for('product_view', item_id=item_id))
        
        # Get all trade requests for this item
        cur.execute('''
            SELECT tr.*, u.username as sender_username, u.profile_image as sender_image,
                   u.department, u.user_type, u.year, u.credibility_score
            FROM trade_requests tr
            JOIN users u ON tr.sender_id = u.user_id
            WHERE tr.requested_item_id = %s
            ORDER BY tr.created_at DESC
        ''', (item_id,))
        trade_requests = cur.fetchall()
        
        cur.close()
        return render_template('product_trade_requests.html', 
                             item=item, 
                             trade_requests=trade_requests)
        
    except Exception as e:
        print(f"Error loading product trade requests: {e}")
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")
        flash('An error occurred while loading trade requests')
        return redirect(url_for('product_view', item_id=item_id))

if __name__ == '__main__':
    socketio.run(app, debug=True, allow_unsafe_werkzeug=True)