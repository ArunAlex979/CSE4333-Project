# TraffiLite Flask App

TraffiLite is a pared-down vehicle-count dashboard built with Flask.

## Project Structure

```
traffilite/
├─ app.py
├─ data.json
├─ blueprints/
│   ├ home.py
│   ├ site.py
│   └ manage.py
├─ templates/
│   ├ base.html
│   ├ home.html
│   ├ site_detail.html
│   ├ manage_list.html
│   └ manage_edit.html
└─ static/
    ├ js/chart-init.js
    └ css/custom.css
```

## Setup and Installation

1.  **Create a virtual environment (if you haven't already):**

    ```bash
    python -m venv .venv
    ```

2.  **Activate the virtual environment:**

    *   On Windows:

        ```bash
        .venv\Scripts\activate
        ```

    *   On macOS/Linux:

        ```bash
        source .venv/bin/activate
        ```

3.  **Install dependencies:**

    ```bash
    pip install -r requirements.txt
    ```

## Running the Application

1.  **Ensure your virtual environment is activated.**
2.  **Run the Flask application:**

    ```bash
    python app.py
    ```

    The application will typically run on `http://127.0.0.1:5000/`.

## Using the Manage Data UI

1.  Navigate to the "Manage Data" section from the navigation bar or by going to `http://127.0.0.1:5000/manage/data`.
2.  You will see a list of all vehicle counter sites.
3.  Click the "Edit" button next to the site you wish to modify.
4.  On the edit page, you will see a JSON representation of the site's data in a textarea.
5.  Modify the `name` or `counts` array as needed. Ensure the `counts` array contains exactly 24 numbers.
6.  Click "Save Changes" to update the data. The changes will be saved to `data.json` and reflected in the dashboard.
7.  If there are any validation errors (e.g., invalid JSON, incorrect number of counts), an error message will be displayed.
