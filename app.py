# app.py
import os
import utils
import datetime
import json
import re
import math
import base64 # Import for Base64 encoding
import sqlalchemy # Needed for inspector check
from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, session, abort, g, jsonify
)
from dotenv import load_dotenv
# Import database connection components and SQLAlchemy
from db_connector import engine, SessionLocal # Or import get_db_session
from sqlalchemy import text, func, or_ # Import func for date functions, or_ for queries
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
import functools
from decimal import Decimal, InvalidOperation # For handling costs

# --- App Configuration ---
load_dotenv()
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'a_very_weak_default_secret_key_')
# Optional: Limit upload size (e.g., 16MB)
# app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'} # Allowed image types

# --- Template Context Processor ---
@app.context_processor
def inject_now():
    # Injects the current UTC datetime into the template context.
    return {'now': datetime.datetime.now(datetime.UTC)} # Use timezone-aware UTC time

# --- Decorators ---
def login_required(view):
    # Custom decorator to require login for accessing certain routes.
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if 'user_id' not in session:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for('login', next=request.url))

        # Fetch unread message count and add to g.user
        user_id = session.get('user_id')
        unread_count = 0
        if user_id and engine:
             try:
                 with engine.connect() as connection:
                     # Check if chat_messages table exists before querying
                     inspector = sqlalchemy.inspect(engine)
                     if inspector.has_table("chat_messages"):
                         sql_unread = text("SELECT COUNT(*) FROM chat_messages WHERE recipient_id = :user_id AND is_read = 0")
                         unread_count = connection.execute(sql_unread, {"user_id": user_id}).scalar_one_or_none() or 0
                     else:
                         print("Warning: chat_messages table not found. Skipping unread count.")
             except Exception as e:
                 print(f"Error fetching unread count for user {user_id}: {e}") # Log error but continue

        g.user = {
            'id': user_id,
            'username': session.get('username'),
            'role': session.get('role'),
            'unread_messages': unread_count # Add unread count to g
        }
        return view(**kwargs)
    return wrapped_view

def admin_required(view):
    # Custom decorator to require admin role for accessing certain routes.
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        # Check if logged in first
        if 'user_id' not in session:
             flash("Please log in to access this page.", "warning")
             return redirect(url_for('login', next=request.url))
        # Check if user has admin role
        if session.get('role') != 'admin':
            flash("You do not have permission to access this page.", "danger")
            abort(403) # Forbidden
        # Ensure g.user is set if not already done by login_required being applied first
        if not hasattr(g, 'user') or g.user is None: # Check if g.user needs initialization
             user_id = session.get('user_id')
             unread_count = 0
             if user_id and engine:
                 try:
                     with engine.connect() as connection:
                         inspector = sqlalchemy.inspect(engine)
                         if inspector.has_table("chat_messages"):
                             sql_unread = text("SELECT COUNT(*) FROM chat_messages WHERE recipient_id = :user_id AND is_read = 0")
                             unread_count = connection.execute(sql_unread, {"user_id": user_id}).scalar_one_or_none() or 0
                         else:
                              print("Warning: chat_messages table not found. Skipping unread count.")
                 except Exception as e:
                     print(f"Error fetching unread count for user {user_id}: {e}")
             g.user = {
                'id': user_id,
                'username': session.get('username'),
                'role': session.get('role'),
                'unread_messages': unread_count
             }
        return view(**kwargs)
    return wrapped_view

# --- Helper Function ---
def is_valid_hex_color(color_code):
    """Checks if a string is a valid 3 or 6 digit hex color code."""
    if not color_code or not isinstance(color_code, str): return False
    match = re.fullmatch(r'^#?([a-fA-F0-9]{6}|[a-fA-F0-9]{3})$', color_code)
    return match is not None

def get_text_color_for_bg(hex_color):
    """Determines if text should be light or dark based on background hex color."""
    if not is_valid_hex_color(hex_color): return '#FFFFFF'
    hex_color = hex_color.lstrip('#')
    if len(hex_color) == 3: hex_color = "".join([c*2 for c in hex_color])
    try:
        r = int(hex_color[0:2], 16); g = int(hex_color[2:4], 16); b = int(hex_color[4:6], 16)
        luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
        return '#000000' if luminance > 0.5 else '#FFFFFF'
    except ValueError: return '#FFFFFF'

def truncate_description(description):
    """Truncates description at the first occurrence of $, -, or ("""
    if not description: return description
    delimiters = ['$', '-', '(']
    first_index = -1
    for char in delimiters:
        index = description.find(char)
        if index != -1:
            if first_index == -1 or index < first_index: first_index = index
    if first_index != -1: return description[:first_index].strip()
    else: return description

def allowed_file(filename):
    """Checks if the file extension is allowed."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- Routes ---
# ... (Login, Logout, Dashboard, Overview, API, Admin routes...) ...
@app.route('/login', methods=['GET', 'POST'])
def login():
    # Handles user login using the external MySQL database.
    if 'user_id' in session: return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username_input = request.form.get('username'); password_input = request.form.get('password'); user_data = None
        if not username_input or not password_input: flash("Username and password are required.", "danger"); return redirect(url_for('login'))
        if not engine: flash("Database connection is not available.", "danger"); return render_template('login.html')
        try:
            with engine.connect() as connection:
                # Uses 'id', 'userName', 'password', 'role' columns
                sql = text("SELECT id, userName AS username, password, role FROM users WHERE userName = :username_param LIMIT 1")
                result = connection.execute(sql, {"username_param": username_input}); user_row = result.fetchone();
                if user_row: user_data = user_row._asdict()
        except SQLAlchemyError as e: print(f"DB error during login: {e}"); flash("An error occurred during login.", "danger"); return render_template('login.html')
        except Exception as e: print(f"Unexpected error during login: {e}"); flash("An unexpected error occurred.", "danger"); return render_template('login.html')

        stored_hash = user_data.get('password') if user_data else None
        if user_data and stored_hash and utils.verify_password(stored_hash, password_input):
            session.clear(); session['user_id'] = user_data.get('id'); session['username'] = user_data.get('username'); session['role'] = user_data.get('role')
            flash(f"Welcome back, {session['username']}!", "success"); next_page = request.args.get('next'); return redirect(next_page or url_for('dashboard'))
        else: flash("Invalid username or password.", "danger"); return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    # Logs the user out by clearing the session.
    session.clear(); flash("You have been logged out.", "info"); return redirect(url_for('login'))

@app.route('/')
@login_required
def dashboard():
    # Shows the main dashboard after login, fetching summary data from MySQL.
    dashboard_data = {"username": g.user.get('username', 'User')}
    page = request.args.get('page', 1, type=int); search_term = request.args.get('search', '', type=str).strip(); per_page = 20
    total_items = 0; total_pages = 0
    autospa_services = [] # For PO Modal

    if not engine: flash("Database connection is not available.", "danger"); dashboard_data['units_list'] = []; dashboard_data['pagination'] = None
    else:
        try:
            with engine.connect() as connection:
                today_date = datetime.date.today()
                # Dashboard Counts
                # Count distinct stockNumbers with complete=1 in jobs
                sql_detail_units = text("SELECT COUNT(DISTINCT stockNumber) FROM jobs WHERE complete = 1")
                detail_units_count = connection.execute(sql_detail_units).scalar_one_or_none() or 0; dashboard_data['units_in_detail'] = detail_units_count
                sql_ready_pickup = text("SELECT COUNT(*) FROM test_db WHERE location = 'Ready for Pickup'"); ready_pickup_count = connection.execute(sql_ready_pickup).scalar_one_or_none() or 0; dashboard_data['ready_pickup_count'] = ready_pickup_count
                # Count notes added today (assuming 'dateTime' column exists)
                sql_notes_today = text("SELECT COUNT(*) FROM notes WHERE DATE(dateTime) = :today")
                notes_today_count = connection.execute(sql_notes_today, {"today": today_date}).scalar_one_or_none() or 0
                dashboard_data['notes_today_count'] = notes_today_count

                # Fetch Autospa Services for PO Modal
                sql_services = text("SELECT service, cost FROM AutospaPricing ORDER BY service")
                services_result = connection.execute(sql_services)
                autospa_services = services_result.mappings().all()

                # Filtered Units Table (Using ROW_NUMBER to prevent duplicates)
                base_where_clauses = []; params = {}
                locations_to_exclude = ['FrontLine', 'sold', 'Deleted', 'Delivered'];
                if locations_to_exclude: formatted_locations = ",".join([f"'{loc}'" for loc in locations_to_exclude]); base_where_clauses.append(f"t.location NOT IN ({formatted_locations})")
                if search_term:
                    search_like = f"%{search_term}%"; params['search'] = search_like
                    search_conditions = [ "t.stockNumber LIKE :search", "t.vin LIKE :search", "CAST(t.year AS CHAR) LIKE :search", "t.make LIKE :search", "t.model LIKE :search", "t.location LIKE :search" ]
                    base_where_clauses.append(f"({' OR '.join(search_conditions)})")
                where_sql = "";
                if base_where_clauses: where_sql = "WHERE " + " AND ".join(base_where_clauses)

                # Count distinct units using ROW_NUMBER
                count_sql_string = f"""
                    WITH RankedUnits AS (
                        SELECT
                            t.stockNumber,
                            ROW_NUMBER() OVER(PARTITION BY t.stockNumber ORDER BY t.id DESC) as rn
                        FROM test_db t
                        {where_sql}
                    )
                    SELECT COUNT(*)
                    FROM RankedUnits
                    WHERE rn = 1
                """
                count_sql = text(count_sql_string)
                count_params = {"search": params['search']} if 'search' in params else {}
                total_items = connection.execute(count_sql, count_params).scalar_one()
                total_pages = math.ceil(total_items / per_page)
                offset = (page - 1) * per_page

                # Fetch distinct units using ROW_NUMBER
                data_sql_string = f"""
                    WITH RankedUnits AS (
                        SELECT
                            t.id, t.stockNumber, t.vin, t.year, t.make, t.model, t.location, t.dateIn, rs.color as location_color,
                            ROW_NUMBER() OVER(PARTITION BY t.stockNumber ORDER BY t.id DESC) as rn
                        FROM test_db t
                        LEFT JOIN reconStatus rs ON t.location = rs.status
                        {where_sql}
                    )
                    SELECT id, stockNumber, vin, year, make, model, location, dateIn, location_color
                    FROM RankedUnits
                    WHERE rn = 1
                    ORDER BY dateIn DESC
                    LIMIT :limit OFFSET :offset
                """
                data_sql = text(data_sql_string)
                params['limit'] = per_page
                params['offset'] = offset

                units_result = connection.execute(data_sql, params); units_list_processed = []
                for unit in units_result.mappings().all():
                    unit_dict = dict(unit); location_color = unit_dict.get('location_color'); unit_dict['text_color'] = get_text_color_for_bg(location_color)
                    if is_valid_hex_color(location_color) and not location_color.startswith('#'): unit_dict['location_color'] = '#' + location_color
                    elif not is_valid_hex_color(location_color): unit_dict['location_color'] = None
                    units_list_processed.append(unit_dict)

                dashboard_data['units_list'] = units_list_processed
                dashboard_data['pagination'] = { 'page': page, 'per_page': per_page, 'total_items': total_items, 'total_pages': total_pages }; dashboard_data['search_term'] = search_term
        except SQLAlchemyError as e: print(f"DB error fetching dashboard: {e}"); flash("Could not load dashboard data.", "warning"); dashboard_data['units_list'] = []; dashboard_data['pagination'] = None; dashboard_data['search_term'] = search_term
        except Exception as e: print(f"Unexpected error fetching dashboard: {e}"); flash("Error loading dashboard data.", "warning"); dashboard_data['units_list'] = []; dashboard_data['pagination'] = None; dashboard_data['search_term'] = search_term

    return render_template('dashboard.html',
                           data=dashboard_data,
                           autospa_services=autospa_services) # Pass services

# --- Route for Overview Calendar ---
@app.route('/overview')
@login_required
def overview_calendar(): return render_template('overview.html')

# --- API Route for Calendar Events ---
@app.route('/api/overview/events')
@login_required
def api_overview_events():
    start_param = request.args.get('start'); end_param = request.args.get('end')
    try:
        view_start = start_param.split('T')[0] if start_param else None; view_end = end_param.split('T')[0] if end_param else None
        if view_start: datetime.date.fromisoformat(view_start);
        if view_end: datetime.date.fromisoformat(view_end)
    except ValueError: print(f"Invalid date format: start={start_param}, end={end_param}"); return jsonify({"error": "Invalid date format"}), 400
    if not view_start or not view_end: print(f"Missing start/end date: start={start_param}, end={end_param}"); return jsonify({"error": "Missing start or end date parameters"}), 400
    calendar_events = [];
    if not engine: print("API Error: DB connection unavailable."); return jsonify([])
    try:
        with engine.connect() as connection:
            sql = text(""" SELECT nds.stockNumber, nds.step, nds.dateIn, nds.dateOut, ns.color as step_color FROM newDaysInStep nds LEFT JOIN newStatus ns ON nds.step = ns.status WHERE nds.dateIn IS NOT NULL AND nds.dateIn < :end_dt AND (nds.dateOut IS NULL OR nds.dateOut > :start_dt) ORDER BY nds.dateIn """)
            result = connection.execute(sql, {"start_dt": view_start, "end_dt": view_end}); step_data = result.mappings().all()
            default_bg_color = '#3B82F6'
            for item in step_data:
                start_date_obj = item.get('dateIn'); end_date_obj = item.get('dateOut'); step_name = str(item.get('step', ''))
                start_str = None; end_str = None
                if isinstance(start_date_obj, (datetime.date, datetime.datetime)): start_str = start_date_obj.strftime('%Y-%m-%d')
                if isinstance(end_date_obj, (datetime.date, datetime.datetime)): end_str = end_date_obj.strftime('%Y-%m-%d')
                db_color = item.get('step_color'); event_color = default_bg_color
                if is_valid_hex_color(db_color): event_color = db_color if db_color.startswith('#') else '#' + db_color
                text_color = get_text_color_for_bg(event_color)
                event = { 'title': str(item.get('stockNumber', 'N/A')), 'start': start_str, 'end': end_str if end_str else None, 'extendedProps': { 'description': step_name }, 'backgroundColor': event_color, 'borderColor': event_color, 'textColor': text_color, 'allDay': True }
                if event['start']: calendar_events.append(event)
    except SQLAlchemyError as e: print(f"DB error fetching API overview events: {e}"); return jsonify([])
    except Exception as e: print(f"Unexpected error fetching API overview events: {e}"); return jsonify([])
    return jsonify(calendar_events)

# --- Admin Routes ---
@app.route('/admin/create_user', methods=['GET', 'POST'])
@login_required
@admin_required
def create_user():
    if request.method == 'POST':
        username_input = request.form.get('username', '').strip(); password_input = request.form.get('password'); confirm_password = request.form.get('confirm_password'); role = request.form.get('role')
        error = False
        if not username_input: flash("Username is required.", "danger"); error = True
        if not password_input: flash("Password is required.", "danger"); error = True
        if password_input != confirm_password: flash("Passwords do not match.", "danger"); error = True
        if role not in ['admin', 'employee']: flash("Invalid role selected.", "danger"); error = True
        if not engine: flash("Database connection is not available.", "danger"); error = True
        if error: return render_template('admin/create_user.html', username=username_input, selected_role=role)
        try: hashed_password_output = utils.hash_password(password_input)
        except Exception as e: print(f"Error hashing password: {e}"); flash("Failed to process password.", "danger"); return render_template('admin/create_user.html', username=username_input, selected_role=role)
        try:
            with engine.connect() as connection:
                sql = text("INSERT INTO users (userName, password, role) VALUES (:username_param, :password_param, :role)")
                with connection.begin(): connection.execute(sql, { "username_param": username_input, "password_param": hashed_password_output, "role": role })
            flash(f"User '{username_input}' created successfully!", "success"); return redirect(url_for('create_user'))
        except IntegrityError: flash(f"Username '{username_input}' already exists.", "danger")
        except SQLAlchemyError as e: print(f"DB error creating user: {e}"); flash("Failed to create user.", "danger")
        except Exception as e: print(f"Unexpected error creating user: {e}"); flash("Error creating user.", "danger")
        return render_template('admin/create_user.html', username=username_input, selected_role=role)
    return render_template('admin/create_user.html')

@app.route('/view_active')
@login_required
def view_active_jobs():
    steps_list = []
    if not engine: flash("Database connection is not available.", "danger")
    else:
        try:
            with engine.connect() as connection:
                current_year = datetime.datetime.now().year
                sql = text(""" SELECT nds.id as step_id, nds.stockNumber, nds.step, nds.dateIn, nds.dateOut, t.year, t.make, t.model FROM newDaysInStep nds LEFT JOIN test_db t ON nds.stockNumber = t.stockNumber WHERE nds.dateIn IS NOT NULL AND nds.dateOut IS NOT NULL AND DATE(nds.dateIn) = DATE(nds.dateOut) AND YEAR(nds.dateIn) = :current_year ORDER BY nds.dateIn DESC LIMIT 100 """)
                result = connection.execute(sql, {"current_year": current_year}); steps_list = result.mappings().all()
        except SQLAlchemyError as e: print(f"DB error fetching active steps list: {e}"); flash("Could not load active steps list.", "danger")
        except Exception as e: print(f"Unexpected error fetching active steps list: {e}"); flash("Error loading active steps list.", "danger")
    return render_template('view_active.html', steps=steps_list)

@app.route('/admin/services')
@login_required
@admin_required
def admin_services():
    services_data = []
    if not engine: flash("Database connection is not available.", "danger")
    else:
        try:
            with engine.connect() as connection:
                 sql = text("SELECT id, service, cost FROM AutospaPricing ORDER BY service"); result = connection.execute(sql); services_data = result.mappings().all()
        except SQLAlchemyError as e: print(f"DB error fetching services: {e}"); flash("Could not load services.", "danger")
        except Exception as e: print(f"Unexpected error fetching services: {e}"); flash("Error loading services.", "danger")
    return render_template('admin/services.html', services=services_data)

@app.route('/admin/manage_users')
@login_required
@admin_required
def manage_users():
    """Displays a list of users for admin management."""
    users_list = []
    if not engine:
        flash("Database connection is not available.", "danger")
    else:
        try:
            with engine.connect() as connection:
                # Fetch all users except potentially the super admin if needed
                # Adjust query as necessary
                sql = text("SELECT id, userName, role FROM users ORDER BY userName ASC")
                result = connection.execute(sql)
                users_list = result.mappings().all()
        except SQLAlchemyError as e:
            print(f"DB error fetching users for management: {e}")
            flash("Error fetching user list.", "danger")
        except Exception as e:
            print(f"Unexpected error fetching user list: {e}")
            flash("An unexpected error occurred while fetching users.", "danger")

    return render_template('admin/manage_users.html', users=users_list)

# --- Route for Admin Password Reset ---
@app.route('/admin/reset_password/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def admin_reset_password(user_id):
    """Handles password reset by an admin."""
    new_password = request.form.get('new_password')
    if not new_password:
        flash("New password cannot be empty.", "warning")
        return redirect(url_for('manage_users'))

    # Optional: Add complexity requirements for the new password here

    if not engine:
        flash("Database connection is not available.", "danger")
        return redirect(url_for('manage_users'))

    try:
        # Hash the new password
        hashed_password_output = utils.hash_password(new_password)

        with engine.connect() as connection:
            with connection.begin():
                # Get username for flash message (optional)
                sql_get_user = text("SELECT userName FROM users WHERE id = :uid")
                username = connection.execute(sql_get_user, {"uid": user_id}).scalar_one_or_none()

                # Update the password
                sql_update = text("UPDATE users SET password = :new_hash WHERE id = :uid")
                result = connection.execute(sql_update, {"new_hash": hashed_password_output, "uid": user_id})

                if result.rowcount > 0:
                    flash(f"Password for user '{username or user_id}' updated successfully.", "success")
                else:
                    flash(f"User ID {user_id} not found.", "warning")

    except SQLAlchemyError as e:
        print(f"DB error resetting password for user {user_id}: {e}")
        flash("Database error resetting password.", "danger")
    except Exception as e:
        print(f"Unexpected error resetting password for user {user_id}: {e}")
        flash("An unexpected error occurred while resetting the password.", "danger")

    return redirect(url_for('manage_users'))


# --- Route for Unit Info Page ---
@app.route('/unit/<string:stock_number>')
@login_required
def unit_info(stock_number):
    """Displays details for a specific unit."""
    unit_details = { "stockNumber": stock_number }
    steps_history = []
    notes_list = []
    current_jobs = []
    tech_list = []
    inventory_exists = False
    inventory_data = None
    checkout_complete = False
    images = []
    pos = []
    autospa_services = [] # For PO Modal
    unit_chats = [] # Initialize chat list

    if not engine: flash("Database connection is not available.", "danger")
    else:
        try:
            with engine.connect() as connection:
                # Fetch main unit info
                sql_main = text("SELECT * FROM test_db WHERE stockNumber = :sn LIMIT 1")
                result_main = connection.execute(sql_main, {"sn": stock_number}); unit_db_data = result_main.mappings().first()
                if unit_db_data: unit_details.update(unit_db_data)
                else: flash(f"Could not find details for unit {stock_number}.", "warning")

                # Fetch latest inventory data (if exists)
                sql_get_inv = text("""
                    SELECT stockNumber, lockingNutsIn, manualsIn, jacksIn, tunneauCoverIn,
                           floorMatsIn, cargoMatsIn, blockHeaterCordIn, changed,
                           lockingNutsOut, manualsOut, jacksOut, tunneauCoverOut,
                           floorMatsOut, cargoMatsOut, blockHeaterCordOut, checkOut
                    FROM unitInventory WHERE stockNumber = :sn ORDER BY changed DESC LIMIT 1
                """)
                inventory_result = connection.execute(sql_get_inv, {"sn": stock_number})
                inventory_data = inventory_result.mappings().first()
                inventory_exists = inventory_data is not None
                if inventory_data and inventory_data.get('checkOut') == 1:
                    checkout_complete = True

                # Fetch Images
                sql_images = text("SELECT image FROM images WHERE stockNumber = :sn ORDER BY id")
                images_result = connection.execute(sql_images, {"sn": stock_number})
                images = [row['image'] for row in images_result.mappings().all()]

                # Fetch steps history
                sql_steps = text("SELECT id, step, dateIn, dateOut FROM newDaysInStep WHERE stockNumber = :sn ORDER BY dateIn DESC")
                steps_result = connection.execute(sql_steps, {"sn": stock_number}); steps_history = steps_result.mappings().all()
                # Fetch notes
                sql_notes = text("SELECT id, notes, dateTime, status FROM notes WHERE stockNumber = :sn ORDER BY dateTime DESC")
                notes_result = connection.execute(sql_notes, {"sn": stock_number}); notes_list = notes_result.mappings().all()
                # Fetch current jobs from JOBS table
                sql_current_jobs = text(""" SELECT j.id as job_id, j.status, j.dateAdded, j.job1, j.priority, j.notes as job_notes, j.tech as assigned_tech_id, tech.techName as assigned_tech_name
                                            FROM jobs j LEFT JOIN techs tech ON j.tech = tech.techNumber
                                            WHERE j.stockNumber = :sn AND (j.status IS NULL OR j.status != 'Completed') ORDER BY j.dateAdded DESC """)
                jobs_result = connection.execute(sql_current_jobs, {"sn": stock_number})
                processed_jobs = []
                for job in jobs_result.mappings().all():
                    job_dict = dict(job)
                    original_job1 = job_dict.get('job1')
                    job_dict['job_description_display'] = truncate_description(original_job1)
                    processed_jobs.append(job_dict)
                current_jobs = processed_jobs

                # Fetch list of techs for assignment dropdown
                sql_techs = text("SELECT techNumber, techName FROM techs ORDER BY techName")
                techs_result = connection.execute(sql_techs); tech_list = techs_result.mappings().all()

                # Fetch POs
                sql_pos = text("""
                    SELECT po, dateIn, service, status
                    FROM preApproved
                    WHERE stockNumber = :sn
                    ORDER BY dateIn DESC
                """)
                pos_result = connection.execute(sql_pos, {"sn": stock_number})
                pos = pos_result.mappings().all()

                # Fetch Autospa Services for PO Modal
                sql_services = text("SELECT service, cost FROM AutospaPricing ORDER BY service")
                services_result = connection.execute(sql_services)
                autospa_services = services_result.mappings().all()

                # Fetch chat messages related to this stock number
                inspector = sqlalchemy.inspect(engine)
                if inspector.has_table("chat_messages"):
                    sql_chats = text("""
                        SELECT cm.message_id, cm.sender_id, cm.recipient_id, cm.message_text, cm.timestamp, cm.is_read,
                               sender.userName as sender_username, recipient.userName as recipient_username
                        FROM chat_messages cm
                        JOIN users sender ON cm.sender_id = sender.id
                        JOIN users recipient ON cm.recipient_id = recipient.id
                        WHERE cm.stockNumber = :sn
                        ORDER BY cm.timestamp ASC
                    """)
                    chats_result = connection.execute(sql_chats, {"sn": stock_number})
                    unit_chats = chats_result.mappings().all()
                else:
                    print("Warning: chat_messages table not found. Skipping chat fetch for unit info.")


        except Exception as e: print(f"Error fetching unit details for {stock_number}: {e}"); flash("Could not load all unit details.", "warning")

    # Pass all data to the template
    return render_template('unit_info.html',
                           unit=unit_details,
                           steps=steps_history,
                           notes=notes_list,
                           jobs=current_jobs,
                           techs=tech_list,
                           inventory_exists=inventory_exists,
                           inventory_data=inventory_data,
                           checkout_complete=checkout_complete,
                           images=images,
                           pos=pos,
                           autospa_services=autospa_services,
                           unit_chats=unit_chats) # <-- Pass chats




# --- Route for Ready for Pickup List ---
@app.route('/ready_pickup')
@login_required
def ready_for_pickup():
    """Displays a list of units with location 'Ready for Pickup'."""
    units_list = []
    if not engine: flash("Database connection is not available.", "danger")
    else:
        try:
            with engine.connect() as connection:
                sql = text(""" SELECT id, stockNumber, vin, year, make, model, location, dateIn FROM test_db WHERE location = 'Ready for Pickup' ORDER BY dateIn DESC """)
                result = connection.execute(sql); units_list = result.mappings().all()
        except SQLAlchemyError as e: print(f"DB error fetching ready for pickup list: {e}"); flash("Could not load ready for pickup list.", "danger")
        except Exception as e: print(f"Unexpected error fetching ready for pickup list: {e}"); flash("Error loading ready for pickup list.", "danger")
    # Assumes templates/ready_pickup.html exists
    return render_template('ready_pickup.html', units=units_list)

# --- Other Unit Routes (pickup, assign_job, stock_in, check_out, add_image, add_note, notes_history, create_po) ---
@app.route('/unit/pickup/<string:stock_number>', methods=['POST'])
@login_required
def unit_pickup(stock_number):
    """Updates the unit's location and access2 when picked up."""
    if not engine: flash("Database connection is not available.", "danger"); return redirect(url_for('ready_for_pickup'))
    try:
        with engine.connect() as connection:
            with connection.begin():
                sql = text(""" UPDATE test_db SET location = :new_location, access2 = :new_access2 WHERE stockNumber = :stock_num """)
                result = connection.execute(sql, { "new_location": "Autospa Pickup", "new_access2": "Autosp Admin", "stock_num": stock_number })
                if result.rowcount > 0: flash(f"Unit {stock_number} marked as picked up.", "success")
                else: flash(f"Unit {stock_number} not found or already updated.", "warning")
    except SQLAlchemyError as e: print(f"DB error updating unit {stock_number}: {e}"); flash("Database error marking unit as picked up.", "danger")
    except Exception as e: print(f"Unexpected error updating unit {stock_number}: {e}"); flash("An unexpected error occurred.", "danger")
    return redirect(url_for('ready_for_pickup'))

@app.route('/job/assign/<int:job_id>', methods=['POST'])
@login_required
def assign_job(job_id):
    """Assigns a tech and sets priority for a specific job in the JOBS table."""
    tech_id = request.form.get('tech_id')
    priority = request.form.get('priority') # Get priority from form
    stock_number = None
    if not tech_id: flash("No technician selected.", "warning"); return redirect(request.referrer or url_for('dashboard'))
    if priority is None: priority = '' # Store empty string if nothing entered
    if not engine: flash("Database connection is not available.", "danger"); return redirect(request.referrer or url_for('dashboard'))
    try:
        with engine.connect() as connection:
            with connection.begin():
                # Get stock number from JOBS table
                sql_get_stock = text("SELECT stockNumber FROM jobs WHERE id = :jid LIMIT 1")
                stock_result = connection.execute(sql_get_stock, {"jid": job_id}).scalar_one_or_none()
                if stock_result: stock_number = stock_result
                else: flash(f"Job ID {job_id} not found.", "danger"); return redirect(url_for('dashboard'))
                # Update JOBS table with tech and priority
                sql_update = text("UPDATE jobs SET tech = :tid, priority = :priority WHERE id = :jid")
                result = connection.execute(sql_update, {"tid": tech_id, "jid": job_id, "priority": priority})
                if result.rowcount > 0:
                    sql_tech_name = text("SELECT techName FROM techs WHERE techNumber = :tid LIMIT 1")
                    tech_name = connection.execute(sql_tech_name, {"tid": tech_id}).scalar_one_or_none() or f"Tech ID {tech_id}"
                    flash(f"Job {job_id} assigned to {tech_name} with priority '{priority}'.", "success")
                else: flash(f"Could not update Job ID {job_id}.", "warning")
    except SQLAlchemyError as e: print(f"DB error assigning job {job_id}: {e}"); flash("Database error assigning job.", "danger")
    except Exception as e: print(f"Unexpected error assigning job {job_id}: {e}"); flash("An unexpected error occurred.", "danger")
    if stock_number: return redirect(url_for('unit_info', stock_number=stock_number))
    else: return redirect(url_for('dashboard'))

@app.route('/unit/stock_in/<string:stock_number>', methods=['POST'])
@login_required
def stock_in_unit(stock_number):
    """Handles submission of the stock-in inventory checklist."""
    print(f"DEBUG (stock_in_unit): Received POST for stock number {stock_number}")
    if not engine: flash("Database connection is not available.", "danger"); return redirect(url_for('unit_info', stock_number=stock_number))
    try:
        with engine.connect() as connection:
            with connection.begin(): # Start transaction
                print(f"DEBUG (stock_in_unit): Checking existing inventory...")
                sql_check = text("SELECT COUNT(*) FROM unitInventory WHERE stockNumber = :sn")
                count = connection.execute(sql_check, {"sn": stock_number}).scalar_one()
                print(f"DEBUG (stock_in_unit): Existing inventory count: {count}")
                if count > 0:
                    flash(f"Inventory checklist already submitted for unit {stock_number}. Cannot submit again.", "warning")
                    return redirect(url_for('unit_info', stock_number=stock_number))

                # Prepare data dictionary for INSERT (saving count to ...In columns)
                form_data = {
                    'stockNumber': stock_number,
                    'lockingNutsIn': 1 if 'lockingNutsIn' in request.form else 0,
                    'manualsIn': 1 if 'manualsIn' in request.form else 0,
                    'jacksIn': 1 if 'jacksIn' in request.form else 0,
                    'tunneauCoverIn': 1 if 'tunneauCoverIn' in request.form else 0,
                    'blockHeaterCordIn': 1 if 'blockHeaterCordIn' in request.form else 0,
                    'floorMatsIn': request.form.get('floorMatsCount', 0, type=int), # Save count directly
                    'cargoMatsIn': request.form.get('cargoMatsCount', 0, type=int), # Save count directly
                    'changed': datetime.datetime.now(datetime.UTC) # Use timezone-aware UTC
                }
                # Construct INSERT statement
                sql = text("""
                    INSERT INTO unitInventory (
                        stockNumber, lockingNutsIn, manualsIn, jacksIn, tunneauCoverIn,
                        floorMatsIn, cargoMatsIn, blockHeaterCordIn, changed
                    ) VALUES (
                        :stockNumber, :lockingNutsIn, :manualsIn, :jacksIn, :tunneauCoverIn,
                        :floorMatsIn, :cargoMatsIn, :blockHeaterCordIn, :changed
                    )
                """)
                print(f"DEBUG (stock_in_unit): Attempting to insert inventory. Data: {form_data}")
                connection.execute(sql, form_data)
                print(f"DEBUG (stock_in_unit): INSERT appeared successful.")
                # Transaction commits automatically here if no exception
        flash(f"Inventory checklist saved for unit {stock_number}.", "success")
    except SQLAlchemyError as e: print(f"DB error saving inventory for {stock_number}: {e}"); flash("Database error saving inventory checklist.", "danger")
    except Exception as e: print(f"Unexpected error saving inventory for {stock_number}: {e}"); flash("An unexpected error occurred while saving inventory.", "danger")
    return redirect(url_for('unit_info', stock_number=stock_number))

@app.route('/unit/check_out/<string:stock_number>', methods=['POST'])
@login_required
def check_out_unit(stock_number):
    """Handles submission of the check-out inventory checklist."""
    print(f"DEBUG (check_out_unit): Received POST for stock number {stock_number}")
    if not engine: flash("Database connection is not available.", "danger"); return redirect(url_for('unit_info', stock_number=stock_number))

    try:
        # Prepare data for UPDATE
        update_data = {
            'stock_num': stock_number,
            'lockingNutsOut': 1 if 'lockingNutsOut' in request.form else 0,
            'manualsOut': 1 if 'manualsOut' in request.form else 0,
            'jacksOut': 1 if 'jacksOut' in request.form else 0,
            'tunneauCoverOut': 1 if 'tunneauCoverOut' in request.form else 0,
            'floorMatsOut': request.form.get('floorMatsOutCount', 0, type=int), # Get count
            'cargoMatsOut': request.form.get('cargoMatsOutCount', 0, type=int), # Get count
            'blockHeaterCordOut': 1 if 'blockHeaterCordOut' in request.form else 0,
            'checkOut': 1, # Mark as checked out
            'changed': datetime.datetime.now(datetime.UTC) # Use timezone-aware UTC
        }

        # Construct UPDATE statement
        sql = text("""
            UPDATE unitInventory SET
                lockingNutsOut = :lockingNutsOut, manualsOut = :manualsOut, jacksOut = :jacksOut,
                tunneauCoverOut = :tunneauCoverOut, floorMatsOut = :floorMatsOut, cargoMatsOut = :cargoMatsOut,
                blockHeaterCordOut = :blockHeaterCordOut, checkOut = :checkOut, changed = :changed
            WHERE stockNumber = :stock_num
        """)

        with engine.connect() as connection:
            with connection.begin(): # Use transaction
                print(f"DEBUG (check_out_unit): Attempting to update inventory. Data: {update_data}")
                result = connection.execute(sql, update_data)
                print(f"DEBUG (check_out_unit): UPDATE result rowcount: {result.rowcount}")
                if result.rowcount > 0: flash(f"Check-out checklist saved for unit {stock_number}.", "success")
                else: flash(f"Could not find inventory record for unit {stock_number} to update.", "warning")

    except SQLAlchemyError as e: print(f"DB error saving check-out for {stock_number}: {e}"); flash("Database error saving check-out checklist.", "danger")
    except Exception as e: print(f"Unexpected error saving check-out for {stock_number}: {e}"); flash("An unexpected error occurred while saving check-out.", "danger")

    return redirect(url_for('unit_info', stock_number=stock_number))

@app.route('/unit/add_image/<string:stock_number>', methods=['POST'])
@login_required
def add_image(stock_number):
    """Handles image upload, encodes to Base64, and saves to DB."""
    if 'image_file' not in request.files: flash('No file part in the request.', 'warning'); return redirect(url_for('unit_info', stock_number=stock_number))
    file = request.files['image_file']
    if file.filename == '': flash('No selected file.', 'warning'); return redirect(url_for('unit_info', stock_number=stock_number))

    if file and allowed_file(file.filename):
        try:
            image_bytes = file.read()
            base64_encoded_data = base64.b64encode(image_bytes)
            base64_string = base64_encoded_data.decode('utf-8')

            image_data = {
                'stockNumber': stock_number,
                'image': base64_string,
            }

            if not engine: flash("Database connection is not available.", "danger"); return redirect(url_for('unit_info', stock_number=stock_number))
            with engine.connect() as connection:
                with connection.begin():
                    sql = text("""
                        INSERT INTO images (stockNumber, image)
                        VALUES (:stockNumber, :image)
                    """)
                    connection.execute(sql, image_data)
            flash('Image uploaded successfully!', 'success')
        except FileNotFoundError: flash('Error reading uploaded file.', 'danger')
        except SQLAlchemyError as e: print(f"DB error saving image for {stock_number}: {e}"); flash('Database error saving image.', 'danger')
        except Exception as e: print(f"Unexpected error saving image for {stock_number}: {e}"); flash('An unexpected error occurred while saving the image.', 'danger')
    else: flash('Invalid file type. Allowed types are: png, jpg, jpeg, gif, webp', 'warning')
    return redirect(url_for('unit_info', stock_number=stock_number))

# --- Route to Handle Note Addition ---
@app.route('/unit/add_note/<string:stock_number>', methods=['POST'])
@login_required
def add_note(stock_number):
    """Handles adding a new note for a unit."""
    note_text = request.form.get('note_text', '').strip()
    if not note_text:
        flash('Note cannot be empty.', 'warning')
        return redirect(url_for('unit_info', stock_number=stock_number))

    if not engine:
        flash("Database connection is not available.", "danger")
        return redirect(url_for('unit_info', stock_number=stock_number))

    try:
        # --- MODIFIED: Prepare data without dateTime, assuming status is INT ---
        note_data = {
            'stockNumber': stock_number,
            'notes': note_text,
            'status': 0 # Assuming 0 represents 'New' status as an integer
            # 'userId': session.get('user_id') # Uncomment if you have this column
        }

        # --- MODIFIED: SQL statement without dateTime ---
        sql = text("""
            INSERT INTO notes (stockNumber, notes, status)
            VALUES (:stockNumber, :notes, :status)
        """)
        # --- END MODIFIED ---

        with engine.connect() as connection:
            with connection.begin():
                print(f"DEBUG (add_note): Attempting to insert note. Data: {note_data}")
                connection.execute(sql, note_data)
                print(f"DEBUG (add_note): INSERT appeared successful.")
        flash('Note added successfully.', 'success')

    except SQLAlchemyError as e:
        print(f"DB error adding note for {stock_number}: {e}")
        flash('Database error adding note.', 'danger')
    except Exception as e:
        print(f"Unexpected error adding note for {stock_number}: {e}")
        flash('An unexpected error occurred while adding the note.', 'danger')

    return redirect(url_for('unit_info', stock_number=stock_number))

# --- Route for Notes History ---
@app.route('/notes_history')
@login_required
def notes_history():
    """Displays notes for a selected date."""
    selected_date_str = request.args.get('date')
    selected_date = None
    notes_for_date = []

    # Validate and parse date, default to today if invalid/missing
    if selected_date_str:
        try:
            selected_date = datetime.datetime.strptime(selected_date_str, '%Y-%m-%d').date()
        except ValueError:
            flash("Invalid date format provided. Showing today's notes.", "warning")
            selected_date = datetime.date.today()
    else:
        selected_date = datetime.date.today()

    # Fetch notes for the selected date
    if not engine:
        flash("Database connection is not available.", "danger")
    else:
        try:
            with engine.connect() as connection:
                # Assuming 'dateTime' column exists and stores date/time
                sql = text("""
                    SELECT stockNumber, notes, dateTime, status
                    FROM notes
                    WHERE DATE(dateTime) = :selected_date
                    ORDER BY dateTime DESC
                """)
                result = connection.execute(sql, {"selected_date": selected_date})
                notes_for_date = result.mappings().all()
        except SQLAlchemyError as e:
            print(f"DB error fetching notes for date {selected_date}: {e}")
            flash("Error fetching notes history.", "danger")
        except Exception as e:
            print(f"Unexpected error fetching notes history: {e}")
            flash("An unexpected error occurred while fetching notes.", "danger")

    return render_template('notes_history.html',
                           notes_list=notes_for_date,
                           selected_date=selected_date.isoformat()) # Pass date as string

# --- Route to Handle PO Creation ---
@app.route('/unit/create_po/<string:stock_number>', methods=['POST'])
@login_required
def create_po(stock_number):
    """Handles PO creation from Dashboard or Unit Info page."""
    po_number = request.form.get('po_number', '').strip()
    source = request.form.get('source', 'unit_info') # Default to unit_info if source isn't passed
    standard_services = request.form.getlist('standard_service') # Gets list of selected service names
    custom_service_names = request.form.getlist('custom_service_name[]')
    custom_service_costs = request.form.getlist('custom_service_cost[]')
    now = datetime.datetime.now(datetime.UTC) # Use timezone-aware UTC

    # --- DEBUGGING: Print received form data ---
    print(f"DEBUG (create_po): Received POST for stock# {stock_number}")
    print(f"DEBUG (create_po): Source = {source}")
    print(f"DEBUG (create_po): PO Number = {po_number}")
    print(f"DEBUG (create_po): Standard Services = {standard_services}")
    print(f"DEBUG (create_po): Custom Names = {custom_service_names}")
    print(f"DEBUG (create_po): Custom Costs = {custom_service_costs}")
    # --- END DEBUGGING ---

    # Basic validation
    if source == 'dashboard' and not po_number:
        flash('PO Number is required when creating from Dashboard.', 'warning')
        return redirect(request.referrer or url_for('dashboard'))
    if not standard_services and not any(s.strip() for s in custom_service_names): # Check if custom names are not just empty strings
        flash('Please select at least one standard service or add a custom service.', 'warning')
        return redirect(request.referrer or url_for('unit_info', stock_number=stock_number))


    if not engine:
        flash("Database connection is not available.", "danger")
        return redirect(request.referrer or url_for('dashboard'))

    services_to_add = [] # List to hold tuples of (service_name, cost)
    cost_map = {}        # Dictionary for standard service costs

    try:
        # --- Step 1: Get costs and compile services (outside transaction) ---
        with engine.connect() as connection: # Connection just for fetching costs
             if standard_services:
                 sql_get_costs = text("SELECT service, cost FROM AutospaPricing")
                 cost_map = {row['service']: row['cost'] for row in connection.execute(sql_get_costs).mappings()}
                 for service_name in standard_services:
                    cost = cost_map.get(service_name)
                    if cost is not None:
                        try:
                            services_to_add.append((service_name, Decimal(cost)))
                        except (InvalidOperation, TypeError):
                             print(f"Warning: Invalid cost format '{cost}' for standard service '{service_name}'. Skipping.")
                             flash(f"Invalid cost format for standard service '{service_name}'. Skipping.", "warning")
                    else:
                        print(f"Warning: Cost not found for standard service '{service_name}'. Skipping.")
                        flash(f"Cost not found for standard service '{service_name}'. Skipping.", "warning")

             # Add custom services
             for i, name in enumerate(custom_service_names):
                name = name.strip()
                if name and i < len(custom_service_costs):
                    try:
                        cost_str = custom_service_costs[i].strip() if custom_service_costs[i] else '0' # Default to '0' if empty string
                        cost = Decimal(cost_str)
                        services_to_add.append((name, cost))
                    except InvalidOperation:
                        print(f"Warning: Invalid cost format '{custom_service_costs[i]}' for custom service '{name}'. Skipping.")
                        flash(f"Invalid cost format for custom service '{name}'. Skipping.", "warning")
                    except IndexError:
                         print(f"Warning: Missing cost for custom service '{name}'. Skipping.")
                         flash(f"Missing cost for custom service '{name}'. Skipping.", "warning")

        # --- Step 2: Validate if there's anything to add ---
        if not services_to_add:
             flash('No valid services to add.', 'warning')
             print("DEBUG (create_po): No valid services compiled.")
             return redirect(request.referrer or url_for('unit_info', stock_number=stock_number))

        print(f"DEBUG (create_po): Compiled services_to_add = {services_to_add}")

        # --- Step 3: Perform inserts within a single transaction ---
        with engine.connect() as connection: # New connection for the transaction
            with connection.begin(): # Start the transaction
                job_status = 'Approved' if source == 'dashboard' else 'Pending'
                print(f"DEBUG (create_po): Determined job_status = {job_status}")

                for service_name, cost in services_to_add:
                    # 1. Insert into jobs table
                    job1_description = service_name # Use only service name

                    # Assumes 'jobs' table has stockNumber, job1, status, priority, complete
                    sql_insert_job = text("""
                        INSERT INTO jobs (stockNumber, job1, status, priority, complete)
                        VALUES (:stockNumber, :job1, :status, :priority, :complete)
                    """)
                    job_params = {
                        'stockNumber': stock_number,
                        'job1': job1_description,
                        'status': job_status,
                        'priority': 0, # Set default priority
                        'complete': 1 # Set complete to 1
                        # 'dateAdded': now, # Removed - Assuming DB handles this
                        # 'poNumber': po_number if po_number else None # Removed - Column doesn't exist
                    }

                    print(f"DEBUG (create_po): Attempting to insert into jobs: {job_params}")
                    connection.execute(sql_insert_job, job_params)
                    print(f"DEBUG (create_po): Inserted into jobs for service: {service_name}")

                    # 2. Insert into preApproved table ONLY if source is dashboard and PO# exists
                    if source == 'dashboard' and po_number:
                        # Assumes 'preApproved' table has stockNumber, po, service, status, dateIn
                        sql_insert_preapproved = text("""
                            INSERT INTO preApproved (stockNumber, po, service, status, dateIn)
                            VALUES (:stockNumber, :po, :service, :status, :dateIn)
                        """)
                        preapp_params = {
                            'stockNumber': stock_number,
                            'po': po_number,
                            'service': service_name, # Use the specific service name
                            'status': 'Approved', # Always Approved for preApproved table
                            'dateIn': now
                        }
                        print(f"DEBUG (create_po): Attempting to insert into preApproved: {preapp_params}")
                        connection.execute(sql_insert_preapproved, preapp_params)
                        print(f"DEBUG (create_po): Inserted into preApproved for service: {service_name}")
                    elif source == 'dashboard':
                         print(f"DEBUG (create_po): Skipping preApproved insert because PO Number is missing (source: dashboard).")
                    else:
                         print(f"DEBUG (create_po): Skipping preApproved insert because source is '{source}'.")

            # Transaction commits here if successful

        flash(f"Successfully added {len(services_to_add)} service(s) as jobs.", "success")
        if source == 'dashboard' and po_number:
             flash(f"PO# {po_number} added to preApproved list.", "info")

    except SQLAlchemyError as e:
        print(f"DB ERROR (create_po): {e}") # Log DB errors
        flash('Database error processing request.', 'danger')
        # Rollback might happen automatically with 'with connection.begin()' on error,
        # but explicitly mentioning it helps understanding.
        print("DB Transaction likely rolled back.")
    except Exception as e:
        print(f"UNEXPECTED ERROR (create_po): {e}") # Log other errors
        flash('An unexpected error occurred.', 'danger')

    # --- Step 4: Redirect ---
    if source == 'dashboard':
        return redirect(url_for('dashboard'))
    else:
        return redirect(url_for('unit_info', stock_number=stock_number))

# --- Route for Completed Jobs by Unit ---
# Using standard decorator registration
@app.route('/completed_jobs')
@login_required
def completed_jobs_by_unit():
    """Displays units with completed jobs and lists those jobs."""
    completed_jobs_grouped = {}
    if not engine:
        flash("Database connection is not available.", "danger")
    else:
        try:
            with engine.connect() as connection:
                # Fetch all jobs marked as complete, ordered by stock number then date
                sql = text("""
                    SELECT j.stockNumber, j.job1, j.dateAdded, j.status
                    FROM jobs j
                    WHERE j.complete = 1
                    ORDER BY j.stockNumber, j.dateAdded DESC
                """)
                result = connection.execute(sql)
                all_completed_jobs = result.mappings().all()

                # Group jobs by stockNumber in Python
                for job in all_completed_jobs:
                    sn = job['stockNumber']
                    if sn not in completed_jobs_grouped:
                        completed_jobs_grouped[sn] = []
                    completed_jobs_grouped[sn].append(job)

        except SQLAlchemyError as e:
            print(f"DB error fetching completed jobs: {e}")
            flash("Error fetching completed jobs list.", "danger")
        except Exception as e:
            print(f"Unexpected error fetching completed jobs list: {e}")
            flash("An unexpected error occurred while fetching completed jobs.", "danger")

    return render_template('completed_jobs_by_unit.html',
                           grouped_jobs=completed_jobs_grouped)

# --- Route for Reports Page ---
@app.route('/reports')
@login_required
def reports_page():
    """Displays various reports."""
    report_data = {}
    # --- Date Range Handling ---
    default_end_date = datetime.date.today()
    default_start_date = default_end_date - datetime.timedelta(days=30)
    start_date_str = request.args.get('start_date', default_start_date.isoformat())
    end_date_str = request.args.get('end_date', default_end_date.isoformat())

    try:
        start_date = datetime.date.fromisoformat(start_date_str)
        end_date = datetime.date.fromisoformat(end_date_str)
        # Ensure end_date is not before start_date
        if end_date < start_date:
            flash("End date cannot be before start date.", "warning")
            end_date = start_date # Or reset both to default
    except ValueError:
        flash("Invalid date format provided. Using default range.", "warning")
        start_date = default_start_date
        end_date = default_end_date
        start_date_str = start_date.isoformat()
        end_date_str = end_date.isoformat()

    report_data['start_date'] = start_date_str
    report_data['end_date'] = end_date_str
    # --- End Date Range Handling ---

    if not engine:
        flash("Database connection is not available.", "danger")
        return render_template('reports.html', reports=report_data)

    try:
        with engine.connect() as connection:
            # --- Report 1: Units Overdue ---
            final_locations = "'FrontLine', 'Sold', 'Delivered', 'Wholesale'" # Adjust as needed
            sql_overdue = text(f"""
                SELECT stockNumber, vin, year, make, model, location, promiseDate
                FROM test_db
                WHERE promiseDate IS NOT NULL
                  AND promiseDate < CURDATE()
                  AND (location IS NULL OR location NOT IN ({final_locations}))
                ORDER BY promiseDate ASC
            """)
            report_data['overdue_units'] = connection.execute(sql_overdue).mappings().all()

            # --- Report 2: Units by Location ---
            sql_locations = text("""
                SELECT location, COUNT(*) as count
                FROM test_db
                GROUP BY location
                ORDER BY location ASC
            """)
            report_data['units_by_location'] = connection.execute(sql_locations).mappings().all()

            # --- Report 3: Average Time in Steps (ALL Steps, with Date Filter) ---
            sql_avg_time = text("""
                SELECT
                    step,
                    AVG(TIMESTAMPDIFF(MINUTE, dateIn, dateOut)) as avg_minutes,
                    COUNT(*) as step_count
                FROM newDaysInStep
                WHERE dateIn IS NOT NULL
                  AND dateOut IS NOT NULL
                  AND dateIn >= :start_date
                  AND dateIn <= :end_date -- Filter by dateIn within the range
                GROUP BY step
                ORDER BY step
            """)
            avg_time_results = connection.execute(sql_avg_time, {
                "start_date": start_date,
                "end_date": end_date
            }).mappings().all()

            # Convert minutes to a more readable format
            processed_avg_times = []
            for row in avg_time_results:
                avg_minutes = row['avg_minutes']
                if avg_minutes is not None:
                    days = int(avg_minutes // (24 * 60))
                    remaining_minutes = avg_minutes % (24 * 60)
                    hours = int(remaining_minutes // 60)
                    minutes = int(remaining_minutes % 60)
                    readable_time = ""
                    if days > 0: readable_time += f"{days}d "
                    if hours > 0: readable_time += f"{hours}h "
                    if minutes > 0 or not readable_time: readable_time += f"{minutes}m"
                    processed_avg_times.append({
                        'step': row['step'],
                        'avg_time_readable': readable_time.strip(),
                        'count': row['step_count']
                    })
                else:
                    processed_avg_times.append({
                        'step': row['step'],
                        'avg_time_readable': 'N/A',
                        'count': row['step_count']
                    })

            report_data['average_step_times'] = processed_avg_times


    except SQLAlchemyError as e:
        print(f"DB error fetching reports: {e}")
        flash("Error generating reports.", "danger")
    except Exception as e:
        print(f"Unexpected error generating reports: {e}")
        flash("An unexpected error occurred while generating reports.", "danger")

    return render_template('reports.html', reports=report_data)


# --- UNCOMMENTED: NEW CHAT ROUTES ---

@app.route('/chat')
@login_required
def chat_page():
    """Renders the main chat interface page."""
    # This page will initially be simple, relying on JS to fetch data via APIs
    return render_template('chat.html')

@app.route('/api/chat/users')
@login_required
def get_chat_users():
    """API endpoint to get a list of users for chat."""
    users_list = []
    current_user_id = g.user.get('id')
    if not engine:
        return jsonify({"error": "Database connection unavailable"}), 500
    try:
        with engine.connect() as connection:
            # Fetch id and userName, excluding the current user
            sql = text("SELECT id, userName FROM users WHERE id != :current_user_id ORDER BY userName ASC")
            result = connection.execute(sql, {"current_user_id": current_user_id})
            users_list = [dict(row) for row in result.mappings().all()] # Convert to list of dicts
    except SQLAlchemyError as e:
        print(f"DB error fetching chat users: {e}")
        return jsonify({"error": "Could not fetch users"}), 500
    except Exception as e:
        print(f"Unexpected error fetching chat users: {e}")
        return jsonify({"error": "An unexpected error occurred"}), 500
    return jsonify(users_list)

@app.route('/api/chat/conversations')
@login_required
def get_conversations():
    """API endpoint to get users the current user has chatted with."""
    conversations = []
    user_id = g.user.get('id')
    if not engine:
        return jsonify({"error": "Database connection unavailable"}), 500
    try:
        with engine.connect() as connection:
            # Find distinct users the current user has sent to or received from
            # Also get the timestamp of the latest message and unread count for each convo
            sql = text("""
                SELECT
                    other_user.id,
                    other_user.userName,
                    MAX(cm.timestamp) AS last_message_time,
                    SUM(CASE WHEN cm.recipient_id = :current_user_id AND cm.is_read = 0 THEN 1 ELSE 0 END) AS unread_count
                FROM chat_messages cm
                JOIN users other_user ON (
                    (cm.sender_id = :current_user_id AND other_user.id = cm.recipient_id) OR
                    (cm.recipient_id = :current_user_id AND other_user.id = cm.sender_id)
                )
                WHERE cm.sender_id = :current_user_id OR cm.recipient_id = :current_user_id
                GROUP BY other_user.id, other_user.userName
                ORDER BY last_message_time DESC;
            """)
            result = connection.execute(sql, {"current_user_id": user_id})
            # Convert Decimal unread_count to int for JSON
            for row in result.mappings().all():
                 convo = dict(row)
                 convo['unread_count'] = int(convo.get('unread_count', 0) or 0)
                 if isinstance(convo.get('last_message_time'), datetime.datetime):
                      convo['last_message_time'] = convo['last_message_time'].isoformat()
                 conversations.append(convo)
    except SQLAlchemyError as e:
        print(f"DB error fetching conversations for user {user_id}: {e}")
        return jsonify({"error": "Could not fetch conversations"}), 500
    except Exception as e:
        print(f"Unexpected error fetching conversations: {e}")
        return jsonify({"error": "An unexpected error occurred"}), 500
    return jsonify(conversations)


@app.route('/api/chat/messages/<int:other_user_id>')
@login_required
def get_messages(other_user_id):
    """API endpoint to get messages between current user and another user."""
    messages = []
    user_id = g.user.get('id')
    if not engine:
        return jsonify({"error": "Database connection unavailable"}), 500
    try:
        with engine.connect() as connection:
            # Begin transaction to fetch messages AND mark them as read
            with connection.begin():
                # Mark messages from the other user to the current user as read
                sql_mark_read = text("""
                    UPDATE chat_messages
                    SET is_read = 1
                    WHERE sender_id = :other_user_id AND recipient_id = :current_user_id AND is_read = 0
                """)
                connection.execute(sql_mark_read, {"other_user_id": other_user_id, "current_user_id": user_id})

                # Fetch the conversation history
                sql_fetch = text("""
                    SELECT cm.message_id, cm.sender_id, cm.recipient_id, cm.message_text, cm.timestamp, cm.stockNumber,
                           sender.userName as sender_username
                    FROM chat_messages cm
                    JOIN users sender ON cm.sender_id = sender.id
                    WHERE (cm.sender_id = :current_user_id AND cm.recipient_id = :other_user_id)
                       OR (cm.sender_id = :other_user_id AND cm.recipient_id = :current_user_id)
                    ORDER BY cm.timestamp ASC
                """)
                result = connection.execute(sql_fetch, {"current_user_id": user_id, "other_user_id": other_user_id})
                # Convert datetime objects to ISO format strings for JSON serialization
                for row in result.mappings().all():
                    message_dict = dict(row)
                    if isinstance(message_dict.get('timestamp'), datetime.datetime):
                        message_dict['timestamp'] = message_dict['timestamp'].isoformat()
                    messages.append(message_dict)

            # Transaction commits here if successful

    except SQLAlchemyError as e:
        print(f"DB error fetching messages between {user_id} and {other_user_id}: {e}")
        return jsonify({"error": "Could not fetch messages"}), 500
    except Exception as e:
        print(f"Unexpected error fetching messages: {e}")
        return jsonify({"error": "An unexpected error occurred"}), 500
    return jsonify(messages)


@app.route('/api/chat/send', methods=['POST'])
@login_required
def send_message():
    """API endpoint to send a new chat message."""
    sender_id = g.user.get('id')
    data = request.get_json()

    if not data:
        return jsonify({"error": "Invalid request data"}), 400

    recipient_id = data.get('recipient_id')
    message_text = data.get('message_text', '').strip()
    stock_number = data.get('stockNumber', '').strip() # Optional stock number

    if not recipient_id or not message_text:
        return jsonify({"error": "Recipient ID and message text are required"}), 400

    # Validate recipient_id (optional but recommended)
    # ... (add check if recipient_id exists in users table) ...

    if not engine:
        return jsonify({"error": "Database connection unavailable"}), 500

    try:
        with engine.connect() as connection:
            with connection.begin():
                sql = text("""
                    INSERT INTO chat_messages (sender_id, recipient_id, message_text, stockNumber)
                    VALUES (:sender_id, :recipient_id, :message_text, :stockNumber)
                """)
                params = {
                    "sender_id": sender_id,
                    "recipient_id": recipient_id,
                    "message_text": message_text,
                    "stockNumber": stock_number if stock_number else None # Store NULL if empty
                }
                result = connection.execute(sql, params)
                # Optionally return the newly created message ID or the message itself
                # last_id = result.lastrowid # This might vary depending on DBAPI driver
                # For simplicity, just return success
    except SQLAlchemyError as e:
        print(f"DB error sending message from {sender_id} to {recipient_id}: {e}")
        return jsonify({"error": "Could not send message"}), 500
    except Exception as e:
        print(f"Unexpected error sending message: {e}")
        return jsonify({"error": "An unexpected error occurred"}), 500

    return jsonify({"success": True, "message": "Message sent"}), 201 # 201 Created

# --- END UNCOMMENTED ---


# --- Error Handling ---
@app.errorhandler(404)
def page_not_found(e): return render_template('errors/404.html'), 404
@app.errorhandler(403)
def forbidden(e): return redirect(url_for('dashboard' if 'user_id' in session else 'login'))
@app.errorhandler(500)
def internal_server_error(e): print(f"Server Error: {e}"); return render_template('errors/500.html'), 500

# --- Main Execution ---
if __name__ == '__main__':
    if engine is None or SessionLocal is None: print("\n--- WARNING: DATABASE CONNECTION FAILED ---\n")
    # Import sqlalchemy here only if needed for the check below
    import sqlalchemy
    app.run(debug=True, host='0.0.0.0', port=5001)

