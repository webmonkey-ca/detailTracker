# main.py
import os
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import database
import utils
import datetime

# --- Add Service Dialog ---
class AddServiceDialog(simpledialog.Dialog):
    """Dialog window for adding a new service."""
    def __init__(self, parent, title="Add New Service"):
        self.name_var = tk.StringVar()
        self.desc_var = tk.StringVar()
        self.price_var = tk.StringVar()
        self.duration_var = tk.StringVar()
        super().__init__(parent, title=title)

    def body(self, master):
        ttk.Label(master, text="Service Name:*").grid(row=0, column=0, sticky="w", padx=5, pady=2)
        self.name_entry = ttk.Entry(master, textvariable=self.name_var, width=40)
        self.name_entry.grid(row=0, column=1, sticky="ew", padx=5, pady=2)

        ttk.Label(master, text="Description:").grid(row=1, column=0, sticky="w", padx=5, pady=2)
        self.desc_entry = ttk.Entry(master, textvariable=self.desc_var, width=40)
        self.desc_entry.grid(row=1, column=1, sticky="ew", padx=5, pady=2)

        ttk.Label(master, text="Base Price ($):*").grid(row=2, column=0, sticky="w", padx=5, pady=2)
        self.price_entry = ttk.Entry(master, textvariable=self.price_var, width=15)
        self.price_entry.grid(row=2, column=1, sticky="w", padx=5, pady=2)

        ttk.Label(master, text="Est. Duration (min):*").grid(row=3, column=0, sticky="w", padx=5, pady=2)
        self.duration_entry = ttk.Entry(master, textvariable=self.duration_var, width=15)
        self.duration_entry.grid(row=3, column=1, sticky="w", padx=5, pady=2)

        self.name_entry.focus_set() # Focus on the first entry field
        return self.name_entry # initial focus

    def validate(self):
        name = self.name_var.get().strip()
        price_str = self.price_var.get().strip()
        duration_str = self.duration_var.get().strip()

        if not name:
            messagebox.showwarning("Input Error", "Service Name is required.", parent=self)
            return False

        self.price = utils.validate_price(price_str)
        if self.price is None:
            messagebox.showwarning("Input Error", "Invalid Base Price. Please enter a non-negative number.", parent=self)
            return False

        self.duration = utils.validate_duration(duration_str)
        if self.duration is None:
            messagebox.showwarning("Input Error", "Invalid Estimated Duration. Please enter a non-negative integer.", parent=self)
            return False

        return True # Validation successful

    def apply(self):
        # This method is called when validate is successful and OK is clicked
        self.result = {
            "name": self.name_var.get().strip(),
            "description": self.desc_var.get().strip(),
            "base_price": self.price,
            "duration": self.duration
        }


# --- Main Application Window ---
class MainWindow(tk.Toplevel):
    def __init__(self, parent, user_role):
        super().__init__(parent)
        self.parent = parent
        self.user_role = user_role
        self.title(f"Detail Shop Tracker ({self.user_role.capitalize()})")
        # Set a minimum size and allow resizing
        self.minsize(800, 600)
        # self.state('zoomed') # Optional: Start maximized

        # --- Style ---
        style = ttk.Style(self)
        style.theme_use('clam') # Use a modern theme ('clam', 'alt', 'default', 'classic')

        # --- Main Structure: Notebook (Tabs) ---
        self.notebook = ttk.Notebook(self)

        # Create frames for each section
        self.jobs_frame = ttk.Frame(self.notebook, padding="10")
        self.bookings_frame = ttk.Frame(self.notebook, padding="10")
        self.checkin_frame = ttk.Frame(self.notebook, padding="10")
        self.quotes_frame = ttk.Frame(self.notebook, padding="10")
        self.pos_frame = ttk.Frame(self.notebook, padding="10")
        self.customers_units_frame = ttk.Frame(self.notebook, padding="10")
        self.admin_frame = ttk.Frame(self.notebook, padding="10") # For admin-only tasks

        # Add tabs to the notebook
        self.notebook.add(self.jobs_frame, text='Jobs & Time')
        self.notebook.add(self.bookings_frame, text='Bookings')
        self.notebook.add(self.customers_units_frame, text='Customers & Units')
        self.notebook.add(self.checkin_frame, text='Check In/Out & Photos')
        self.notebook.add(self.quotes_frame, text='Quotes')
        self.notebook.add(self.pos_frame, text='Purchase Orders')

        # Add admin tab only if user is admin
        if self.user_role == 'admin':
            self.notebook.add(self.admin_frame, text='Admin')
            self.setup_admin_ui() # Populate admin tab

        self.notebook.pack(expand=True, fill='both')

        # --- Populate Core Tabs ---
        self.setup_jobs_ui()
        # self.setup_bookings_ui() # Placeholder - Needs implementation
        # self.setup_customers_units_ui() # Placeholder
        # self.setup_checkin_ui() # Placeholder
        # self.setup_quotes_ui() # Placeholder
        # self.setup_pos_ui() # Placeholder

        # Make window modal and manage closing
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.transient(parent) # Keep window on top of parent
        self.grab_set()       # Make modal (disable parent window)
        parent.wait_window(self) # Wait until this window is destroyed

    def _on_close(self):
        # Ask for confirmation before closing the main window
        if messagebox.askokcancel("Quit", "Do you want to exit the application?", parent=self):
            self.parent.destroy() # Destroy the root (Login) window, which exits the app
            # self.destroy() # Only destroys this window, Login window might remain

    # --- UI Setup Methods ---

    def setup_jobs_ui(self):
        """Sets up the UI elements for the Jobs & Time Tracking tab."""
        # Frame for the list
        list_frame = ttk.LabelFrame(self.jobs_frame, text="Current Jobs Overview", padding="10")
        list_frame.pack(fill="both", expand=True, padx=5, pady=5)

        # Columns for the Treeview
        columns = ("job_id", "status", "booking_date", "make_model", "license", "customer", "employee")
        self.job_tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=15)

        # Define headings
        self.job_tree.heading("job_id", text="Job ID", anchor=tk.W)
        self.job_tree.heading("status", text="Status", anchor=tk.W)
        self.job_tree.heading("booking_date", text="Booked", anchor=tk.W)
        self.job_tree.heading("make_model", text="Vehicle", anchor=tk.W)
        self.job_tree.heading("license", text="Plate", anchor=tk.W)
        self.job_tree.heading("customer", text="Customer", anchor=tk.W)
        self.job_tree.heading("employee", text="Assigned To", anchor=tk.W)


        # Define column widths
        self.job_tree.column("job_id", width=60, stretch=False)
        self.job_tree.column("status", width=100, stretch=False)
        self.job_tree.column("booking_date", width=120, stretch=False)
        self.job_tree.column("make_model", width=150)
        self.job_tree.column("license", width=100)
        self.job_tree.column("customer", width=150)
        self.job_tree.column("employee", width=120)

        # Add Scrollbars
        vsb = ttk.Scrollbar(list_frame, orient="vertical", command=self.job_tree.yview)
        hsb = ttk.Scrollbar(list_frame, orient="horizontal", command=self.job_tree.xview)
        self.job_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        # Grid layout for Treeview and Scrollbars
        self.job_tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        hsb.grid(row=1, column=0, sticky='ew')

        list_frame.grid_rowconfigure(0, weight=1)
        list_frame.grid_columnconfigure(0, weight=1)

        # --- Action Buttons ---
        button_frame = ttk.Frame(self.jobs_frame, padding="5")
        button_frame.pack(fill="x", pady=5)

        refresh_btn = ttk.Button(button_frame, text="Refresh List", command=self.refresh_job_list)
        refresh_btn.pack(side="left", padx=5)

        # Add buttons for: View Details, Assign Employee, Start/Stop Timer etc.
        # These would typically operate on the selected item in the treeview
        # details_btn = ttk.Button(button_frame, text="View Details", command=self.view_job_details) # Implement this
        # details_btn.pack(side="left", padx=5)


        # Initial data load
        self.refresh_job_list()

    def refresh_job_list(self):
        """Clears and reloads the job list from the database."""
        # Delete existing items
        for item in self.job_tree.get_children():
            self.job_tree.delete(item)

        # Fetch new data
        jobs_data = database.get_jobs_overview()
        for job in jobs_data:
            # Handle potential None values gracefully
            make = job['make'] or ''
            model = job['model'] or ''
            make_model = f"{make} {model}".strip()
            plate = job['license_plate'] or 'N/A'
            customer = job['customer_name'] or 'N/A'
            employee = job['employee_name'] or 'Unassigned'
            booking_date_str = job['booking_date'] or ''
            # Format date nicely if needed
            # try:
            #     if booking_date_str:
            #         booking_dt = datetime.datetime.fromisoformat(booking_date_str)
            #         booking_date_str = booking_dt.strftime("%Y-%m-%d %H:%M")
            # except ValueError:
            #     pass # Keep original string if parsing fails

            self.job_tree.insert("", tk.END, values=(
                job['job_id'],
                job['status'],
                booking_date_str,
                make_model,
                plate,
                customer,
                employee
            ))

    # --- Admin UI Setup ---
    def setup_admin_ui(self):
        """Sets up the UI elements for the Admin tab."""
        # --- Service Management Section ---
        service_frame = ttk.LabelFrame(self.admin_frame, text="Manage Services", padding="10")
        service_frame.pack(fill="x", expand=False, padx=5, pady=5) # Changed expand to False

        # Treeview for services
        columns = ("id", "name", "price", "duration")
        self.service_tree = ttk.Treeview(service_frame, columns=columns, show="headings", height=10)
        self.service_tree.heading("id", text="ID")
        self.service_tree.heading("name", text="Service Name")
        self.service_tree.heading("price", text="Price ($)")
        self.service_tree.heading("duration", text="Duration (min)")
        self.service_tree.column("id", width=50, stretch=False, anchor=tk.E)
        self.service_tree.column("name", width=250)
        self.service_tree.column("price", width=100, anchor=tk.E)
        self.service_tree.column("duration", width=100, anchor=tk.E)

        # Scrollbar for service list
        service_vsb = ttk.Scrollbar(service_frame, orient="vertical", command=self.service_tree.yview)
        self.service_tree.configure(yscrollcommand=service_vsb.set)

        self.service_tree.grid(row=0, column=0, sticky='nsew')
        service_vsb.grid(row=0, column=1, sticky='ns')

        service_frame.grid_rowconfigure(0, weight=1)
        service_frame.grid_columnconfigure(0, weight=1)

        # Buttons for services
        service_btn_frame = ttk.Frame(service_frame)
        service_btn_frame.grid(row=1, column=0, columnspan=2, pady=5, sticky='ew')

        add_btn = ttk.Button(service_btn_frame, text="Add Service", command=self.add_new_service)
        add_btn.pack(side="left", padx=5)

        edit_btn = ttk.Button(service_btn_frame, text="Edit Selected", command=self.edit_selected_service, state=tk.DISABLED) # Implement edit
        edit_btn.pack(side="left", padx=5)
        self.edit_service_btn = edit_btn # Keep reference to enable/disable

        delete_btn = ttk.Button(service_btn_frame, text="Delete Selected", command=self.delete_selected_service, state=tk.DISABLED)
        delete_btn.pack(side="left", padx=5)
        self.delete_service_btn = delete_btn # Keep reference

        # Bind selection change to enable/disable buttons
        self.service_tree.bind('<<TreeviewSelect>>', self.on_service_select)

        # --- User/Employee Management Section (Placeholder) ---
        user_frame = ttk.LabelFrame(self.admin_frame, text="Manage Users & Employees", padding="10")
        user_frame.pack(fill="x", expand=False, padx=5, pady=10)
        ttk.Label(user_frame, text="User and Employee management controls go here...").pack()

        # Initial load of services
        self.refresh_service_list()


    def on_service_select(self, event=None):
        """Callback when a service is selected in the Treeview."""
        selected_items = self.service_tree.selection()
        if selected_items:
            # Enable Edit and Delete buttons if an item is selected
            self.edit_service_btn.config(state=tk.NORMAL)
            self.delete_service_btn.config(state=tk.NORMAL)
        else:
            # Disable buttons if no item is selected
            self.edit_service_btn.config(state=tk.DISABLED)
            self.delete_service_btn.config(state=tk.DISABLED)

    def refresh_service_list(self):
        """Clears and reloads the service list in the Admin tab."""
        # Delete existing items
        for item in self.service_tree.get_children():
            self.service_tree.delete(item)
        # Fetch new data
        services = database.get_all_services()
        for service in services:
            self.service_tree.insert("", tk.END, values=(
                service['service_id'],
                service['name'],
                f"{service['base_price']:.2f}", # Format price
                service['estimated_duration_minutes']
            ))
        # After refresh, no item is selected, so disable buttons
        self.on_service_select()

    def add_new_service(self):
        """Opens the dialog to add a new service and refreshes the list."""
        dialog = AddServiceDialog(self)
        if dialog.result: # User clicked OK and validation passed
            new_service = dialog.result
            service_id = database.add_service(
                new_service['name'],
                new_service['description'],
                new_service['base_price'],
                new_service['duration']
            )
            if service_id:
                messagebox.showinfo("Success", f"Service '{new_service['name']}' added successfully.", parent=self)
                self.refresh_service_list()
            else:
                # Error message already printed in database.py or validation failed
                 messagebox.showerror("Error", f"Failed to add service '{new_service['name']}'. Check console for details.", parent=self)

    def edit_selected_service(self):
         """Placeholder for editing a service."""
         selected_items = self.service_tree.selection()
         if not selected_items:
             messagebox.showwarning("Selection Error", "Please select a service to edit.", parent=self)
             return
         # item_id = self.service_tree.focus() # Gets the internal ID of the selected item
         # item_values = self.service_tree.item(item_id, 'values')
         # service_id_to_edit = item_values[0]
         # TODO: Implement an EditServiceDialog similar to AddServiceDialog
         # Pre-populate the dialog with existing values
         # Call a database.update_service function
         messagebox.showinfo("Not Implemented", "Editing services is not yet implemented.", parent=self)


    def delete_selected_service(self):
        """Deletes the selected service from the database after confirmation."""
        selected_items = self.service_tree.selection()
        if not selected_items:
            messagebox.showwarning("Selection Error", "Please select a service to delete.", parent=self)
            return

        item_iid = selected_items[0] # Get the first selected item's internal ID
        item_values = self.service_tree.item(item_iid, 'values')
        service_id_to_delete = item_values[0]
        service_name = item_values[1]

        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete the service:\n'{service_name}' (ID: {service_id_to_delete})?", parent=self):
            deleted = database.delete_service(service_id_to_delete)
            if deleted:
                messagebox.showinfo("Success", f"Service '{service_name}' deleted.", parent=self)
                self.refresh_service_list()
            else:
                messagebox.showerror("Error", f"Failed to delete service '{service_name}'. It might be in use or a database error occurred.", parent=self)


# --- Login Window (Slightly modified to handle main window closing) ---
class LoginWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Login - Detail Shop Tracker")
        self.geometry("350x200")
        self.resizable(False, False)

        # Center the window
        self.eval('tk::PlaceWindow . center')

        # Initialize DB (create tables if needed)
        try:
            database.initialize_database()
        except Exception as e:
             messagebox.showerror("Database Error", f"Failed to initialize database: {e}\nApplication cannot start.")
             self.destroy()
             return

        # Configure grid layout
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=3)

        # Username
        ttk.Label(self, text="Username:").grid(row=0, column=0, padx=10, pady=10, sticky=tk.W)
        self.username_entry = ttk.Entry(self, width=30)
        self.username_entry.grid(row=0, column=1, padx=10, pady=10, sticky=tk.EW)
        self.username_entry.focus() # Start cursor here

        # Password
        ttk.Label(self, text="Password:").grid(row=1, column=0, padx=10, pady=10, sticky=tk.W)
        self.password_entry = ttk.Entry(self, show="*", width=30)
        self.password_entry.grid(row=1, column=1, padx=10, pady=10, sticky=tk.EW)
        self.password_entry.bind("<Return>", self.attempt_login) # Allow login with Enter key

        # Login Button
        self.login_button = ttk.Button(self, text="Login", command=self.attempt_login)
        self.login_button.grid(row=2, column=0, columnspan=2, pady=15)

        # Status Bar (Optional)
        # self.status_var = tk.StringVar()
        # status_bar = ttk.Label(self, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        # status_bar.grid(row=3, column=0, columnspan=2, sticky='ew')

    def attempt_login(self, event=None):
        username = self.username_entry.get().strip()
        password = self.password_entry.get() # Don't strip password

        if not username or not password:
            messagebox.showerror("Login Failed", "Please enter both username and password.", parent=self)
            return

        user_data = database.get_user_by_username(username)

        # Securely verify password
        if user_data and utils.verify_password(user_data['password_hash'], password):
            # messagebox.showinfo("Login Success", f"Welcome, {username}!", parent=self) # Maybe skip this popup
            self.withdraw() # Hide login window BEFORE opening main window
            # Open the main application window - it will handle its own lifecycle
            MainWindow(self, user_data['role'])
            # The main window's _on_close method will handle exiting by destroying self (the login window)

        else:
            messagebox.showerror("Login Failed", "Invalid username or password.", parent=self)
            self.password_entry.delete(0, tk.END) # Clear password field


if __name__ == "__main__":
    # Ensures that database/utils paths work correctly when run as a script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir) # Change current working directory to the script's directory

    app = LoginWindow()
    app.mainloop()
