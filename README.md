# Faculty Workload and Scheduling Application

This Python application helps manage faculty workloads and schedules, providing an interface to track courses, units, and other related data. It uses a PyQt5 GUI and an SQLite database for data storage and retrieval.
- Permission: Ulysses Cabayao, SJ 2024 (uscabayaosj@addu.edu.ph)

## Table of Contents
- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
- [How It Works](#how-it-works)
- [Security](#security)
- [Troubleshooting](#troubleshooting)

## Features
- Track faculty members and their courses.
- Calculate and display faculty workload status.
- Export data to CSV format.
- Dark theme support for better visual comfort.

## Installation

### Prerequisites
- Python 3.x
- PyQt5
- SQLite

### Steps
1. Clone the repository:
    ```sh
    git clone https://github.com/yourusername/faculty-workload.git
    cd faculty-workload
    ```
2. Install the required packages:
    ```sh
    pip install -r requirements.txt
    ```
3. Set up the SQLite database:
    ```sh
    python setup_database.py
    ```

## Usage
1. Run the application:
    ```sh
    python facload.py
    ```
2. Use the GUI to manage faculty and courses, view workload statuses, and export data.

## Security
Ensure your OpenAI API key is stored securely and not exposed in the code. Use environment variables or configuration files with restricted access.

## Troubleshooting
- **Error logs**: Check the logs for any errors during execution.
- **API key setup**: Ensure the OpenAI API key is set up correctly in the script properties.
- **Permissions**: Verify that the document has the necessary permissions for the script to run.

**Note**: This script is for educational purposes only and should not be used for production without proper testing and validation.

## How It Works
The application initializes the GUI using PyQt5 and connects to an SQLite database to store faculty and course data. The main components include:
- **Faculty**: Stores information about faculty members.
- **Course**: Stores information about courses, including units and schedules.
- **FacultyWorkloadApp**: The main application class handling the GUI and interactions.
