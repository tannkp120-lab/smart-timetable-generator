# Timetable Project

This is a Flask-based web application for managing timetables.

## Prerequisites

Before running this project, ensure you have the following installed:

1.  **Python**: [Download Python](https://www.python.org/downloads/) (Make sure to check "Add Python to PATH" during installation).
2.  **XAMPP**: [Download XAMPP](https://www.apachefriends.org/download.html) (for MySQL Database).
3.  **Git**: [Download Git](https://git-scm.com/downloads) (Optional, for cloning).

## Setup Instructions

### 1. Database Setup

1.  Open **XAMPP Control Panel** and start **Apache** and **MySQL**.
2.  Open your browser and go to `http://localhost/phpmyadmin`.
3.  Create a new database named `timetable_db`.
4.  Click on the `timetable_db` database you just created.
5.  Go to the **Import** tab.
6.  Click **Choose File** and select the `timetable_db.sql` file from this project folder.
7.  Click **Import** (or Go) at the bottom.

### 1. Getting the Code

1.  Open a terminal (Command Prompt or PowerShell).
2.  Clone the repository:
    ```bash
    git clone https://github.com/Ayushv7051/TimetableProject.git
    cd TimetableProject
    ```

### 2. Project Installation

1.  Open a terminal (Command Prompt or PowerShell) in the project folder.
2.  (Optional but recommended) Create a virtual environment:
    ```bash
    python -m venv venv
    .\venv\Scripts\activate
    ```
3.  Install the required dependencies:
    ```bash
    pip install -r requirements.txt
    ```

## Running the Application

1.  Make sure XAMPP (MySQL) is running.
2.  In your terminal, run the application:
    ```bash
    python app.py
    ```
3.  You should see output indicating the server is running (usually `Running on http://127.0.0.1:5000`).
4.  Open your browser and go to: [http://127.0.0.1:5000](http://127.0.0.1:5000)

## Default Login Credentials

-   **Admin**: (Check `users` table or register a new one)
-   **Lecturer/Student**: Register via the signup page.

## Troubleshooting

-   **Database Error**: If you see database connection errors, ensure XAMPP MySQL is running and the credentials in `app.py` match your XAMPP settings (default user: `root`, password: ``).
