import os
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import base64
import plotly.express as px
from flask import Flask, render_template, url_for, request, redirect, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from io import BytesIO
from scipy.integrate import simpson
import numpy as np
import pandas as pd
import matplotlib
import shutil  # Import shutil to remove folders
matplotlib.use('Agg')  # Use a non-interactive backend

# Dummy user credentials
USERNAME = "747IR"
PASSWORD = "1234"


app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///test.db' # set-up the database (stored in test.db)
app.config['SECRET_KEY'] = 'supersecretkey'  # Change this to a secure key
db = SQLAlchemy(app) # initialize the database

class Todo(db.Model): # create a class for the database
    id = db.Column(db.Integer, primary_key=True) # create a column for the id
    content = db.Column(db.String(200), nullable=False) # create a column for the content
    completed = db.Column(db.Integer, default=0) # create a column for the completion status
    date_created = db.Column(db.DateTime, default=datetime.utcnow) # create a column for the date created

    def __repr__(self): #every time we create a new task, it will return the id
        return '<Task %r>' % self.id

# ✅ Login Route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Check credentials
        if username == USERNAME and password == PASSWORD:
            session['user'] = username  # Store user in session
            return redirect(url_for('index'))  # Redirect to home page
        else:
            return render_template('login.html', error="Invalid username or password.")

    return render_template('login.html')


# ✅ Logout Route
@app.route('/logout')
def logout():
    session.pop('user', None)  # Remove user from session
    return redirect(url_for('login'))  # Redirect to login page


# ✅ Protect the Home Page - Only logged-in users can access
@app.route('/', methods=['GET', 'POST'])
def index():
    if 'user' not in session:  # Check if user is logged in
        return redirect(url_for('login'))  # Redirect to login page

    base_path = 'input'
    if not os.path.exists(base_path):
        os.makedirs(base_path)

    if request.method == 'POST':  # Create a new folder
        new_folder = request.form.get('new_folder', '').strip()
        if new_folder:
            folder_path = os.path.join(base_path, new_folder)
            if not os.path.exists(folder_path):
                os.makedirs(folder_path)
                return redirect(f"/?folder={new_folder}")

    selected_folder = request.args.get('folder')
    tasks = []
    if selected_folder:
        folder_path = os.path.join(base_path, selected_folder)
        if os.path.exists(folder_path):
            tasks = Todo.query.filter(Todo.content.like(f"{selected_folder}/%")).order_by(Todo.date_created).all()
        else:
            return f"The folder '{selected_folder}' does not exist."

    folders = [f for f in os.listdir(base_path) if os.path.isdir(os.path.join(base_path, f))]

    return render_template('index.html', folders=folders, selected_folder=selected_folder, tasks=tasks)

@app.route('/upload', methods=['POST'])
def upload():
    base_path = 'input'
    folder = request.form.get('folder')

    if not folder:
        return "No folder selected. Please select a folder first."

    folder_path = os.path.join(base_path, folder)
    if not os.path.exists(folder_path):
        return f"Folder '{folder}' does not exist."

    files = request.files.getlist('file')
    for file in files:
        if file and file.filename.endswith('.csv'):
            file_path = os.path.join(folder_path, file.filename)

            if os.path.exists(file_path):
                return f"File '{file.filename}' already exists in folder '{folder}'."

            file.save(file_path)
            new_task = Todo(content=f"{folder}/{file.filename}")
            db.session.add(new_task)

    try:
        db.session.commit()
        return redirect(f"/?folder={folder}")  # Redirect back to home with the selected folder
    except Exception as e:
        return f"There was an issue saving the files: {e}"

    
@app.route('/delete/<int:id>')
def delete(id):
    task_to_delete = Todo.query.get_or_404(id)
    file_path = os.path.join('input', task_to_delete.content)  # Full file path

    # Extract folder name before deleting the file
    folder = os.path.dirname(task_to_delete.content)

    try:
        os.remove(file_path)  # Delete file
        db.session.delete(task_to_delete)  # Delete from database
        db.session.commit()
        return redirect(f"/?folder={folder}")  # Redirect to home with folder context
    except Exception as e:
        return f"There was a problem deleting that task: {e}"

@app.route('/update/<int:id>', methods=['GET', 'POST'])
def update(id):
    task = Todo.query.get_or_404(id)
    old_file_path = os.path.join('input', task.content)  # Full path to the existing file
    folder = os.path.dirname(task.content)  # Extract the folder name

    if not os.path.exists(old_file_path):
        return 'The file does not exist.'

    if request.method == 'POST':
        new_file_name = request.form['content'].strip()  # Get the new file name
        csv_data = request.form.get('csv_data', '').strip()  # Get the updated file content

        if not new_file_name.endswith('.csv'):
            return 'Invalid file name. The new file name must end with ".csv".'

        new_file_path = os.path.join('input', folder, new_file_name)

        try:
            # ✅ Always update the content of the existing file
            with open(old_file_path, 'w', newline='') as f:
                f.write(csv_data)

            # ✅ If the file name changed, rename it and update the database
            if new_file_path != old_file_path:
                os.rename(old_file_path, new_file_path)
                task.content = f"{folder}/{new_file_name}"  # Update database with new file path

            db.session.commit()
            return redirect(f"/?folder={folder}")  # ✅ Redirect to selected folder
        except Exception as e:
            return f'There was an issue updating your file: {e}'

    else:
        base_file_name = os.path.basename(task.content)  # Extract only the filename
        try:
            with open(old_file_path, 'r') as f:
                csv_data = f.read()  # Load the file content

            return render_template('update.html', task=task, csv_data=csv_data, base_file_name=base_file_name, folder=folder)
        except Exception as e:
            return f'There was an issue loading your file: {e}'


@app.route('/read_csv/<int:id>') # read csv file
def read_csv(id):
    task = Todo.query.get_or_404(id)  # Get the task associated with the file
    file_path = os.path.join('input', task.content)  # Path to the uploaded CSV file

    if not os.path.exists(file_path):
        return f"File {task.content} does not exist."

    try:
        # Read the CSV file
        df = pd.read_csv(file_path)
        x_column = df.columns[0]
        y_column = df.columns[1]
        
        # Calculate the maximum transmission value
        max_transmission = df[y_column].max()

        # Create the plot
        fig = px.line(df, x=x_column, y=y_column, title="Interactive Integration Plot with Baseline")
        fig.update_layout(
            xaxis_title=x_column,
            yaxis_title=y_column
        )

        # Add a horizontal baseline at maximum transmission
        fig.add_shape(
            type="line",
            x0=df[x_column].min(),
            x1=df[x_column].max(),
            y0=max_transmission,
            y1=max_transmission,
            line=dict(color="red", width=1, dash="dash"),
            name="Max Transmission"
        )

        plot_html = fig.to_html(full_html=False)

        # Render the template with the plot
        return render_template(
            'read_csv.html',
            plot_html=plot_html
        )
    except Exception as e:
        return f"There was an issue processing the file: {e}"

@app.route('/manual_integration', methods=['POST'])
def manual_integration():
    try:
        data = request.get_json()
        range_min = float(data['range_min'])
        range_max = float(data['range_max'])

        # Resolve file path
        task = Todo.query.get_or_404(1)  # Replace with appropriate task ID
        file_path = os.path.join('input', task.content)

        # Ensure file exists
        if not os.path.exists(file_path):
            return jsonify({"error": "File does not exist"}), 400

        # Read the CSV file
        df = pd.read_csv(file_path)  # Ensure file_path is valid

        x_column = df.columns[0]
        y_column = df.columns[1]
        x_data = df[x_column]
        y_data = df[y_column]

        inverted_x = x_data[::-1]
        inverted_y = y_data[::-1]

        baseline = df[y_column].max()

        # Adjust the data to set the reference baseline at 100%
        adjusted_y = baseline - inverted_y

        # Define the range for integration
        integration_range = (inverted_x >= range_min) & (inverted_x <= range_max)

        # Extract the data within the specified range for the adjusted spectrum
        x_range = inverted_x[integration_range]
        adjusted_y_range = adjusted_y[integration_range]

        # Perform the integration using Simpson's rule on the adjusted spectrum
        adjusted_area = simpson(adjusted_y_range, x_range)


        return jsonify({"integrated_value": adjusted_area})
    except Exception as e:
        print("Error during integration:", str(e))
        return jsonify({"error": str(e)}), 400


@app.route('/plot_combined', methods=['POST'])
def plot_combined():
    selected_files = request.form.getlist('selected_files')  # Retrieve selected files
    if not selected_files:
        return "No files selected. Please select at least one file."

    try:
        import matplotlib.pyplot as plt
        from io import BytesIO
        import os
        import pandas as pd

        # Use a non-interactive backend
        import matplotlib
        matplotlib.use('Agg')

        # Combine and plot data from selected files
        plt.figure(figsize=(10, 6))
        for file_name in selected_files:
            file_path = os.path.join('input', file_name)
            if os.path.exists(file_path):
                df = pd.read_csv(file_path)
                data_x = df[df.columns[0]]
                data_y = df[df.columns[1]]
                inverted_x = data_x[::-1]
                inverted_y = data_y[::-1]

                # Use only the file name in the legend
                plt.plot(inverted_x, inverted_y, label=os.path.basename(file_name))
            else:
                return f"File {file_name} does not exist."

        plt.ylabel("Transmittance")
        plt.xlabel("Wavenumber [$cm^{-1}$]")
        plt.title("Combined Plot of Selected Files")
        plt.legend()
        plt.grid()

        # Save the plot to a file
        combined_plot_path = os.path.join('static', 'combined_plot.png')
        plt.savefig(combined_plot_path)
        plt.close()  # Close the figure to free resources

        # Render the plot on a web page
        return render_template('plot_combined.html', plot_path=combined_plot_path)

    except Exception as e:
        return f"An error occurred while plotting: {e}"
    
@app.route('/rename_folder', methods=['POST'])
def rename_folder():
    base_path = 'input'
    old_folder = request.form.get('old_folder', '').strip()
    new_folder = request.form.get('new_folder', '').strip()

    if not old_folder or not new_folder:
        return "Both old and new folder names are required."

    old_folder_path = os.path.join(base_path, old_folder)
    new_folder_path = os.path.join(base_path, new_folder)

    if not os.path.exists(old_folder_path):
        return f"Folder '{old_folder}' does not exist."

    if os.path.exists(new_folder_path):
        return f"Folder '{new_folder}' already exists. Choose another name."

    try:
        os.rename(old_folder_path, new_folder_path)  # Rename the folder

        # Update database records to reflect new folder name
        tasks = Todo.query.filter(Todo.content.like(f"{old_folder}/%")).all()
        for task in tasks:
            task.content = task.content.replace(f"{old_folder}/", f"{new_folder}/")
        
        db.session.commit()
        return redirect(f"/?folder={new_folder}")  # Redirect to the renamed folder
    except Exception as e:
        return f"There was an issue renaming the folder: {e}"

@app.route('/delete_folder', methods=['POST'])
def delete_folder():
    base_path = 'input'
    folder = request.form.get('folder', '').strip()

    if not folder:
        return "Folder name is required."

    folder_path = os.path.join(base_path, folder)

    if not os.path.exists(folder_path):
        return f"Folder '{folder}' does not exist."

    try:
        # Delete all files inside the folder from the database
        Todo.query.filter(Todo.content.like(f"{folder}/%")).delete()
        db.session.commit()

        # Remove the folder and its contents
        shutil.rmtree(folder_path)  # Deletes the folder and its contents
        return redirect("/")  # Redirect to home after deletion
    except Exception as e:
        return f"There was an issue deleting the folder: {e}"



if __name__ == '__main__':
    app.run(debug=True)