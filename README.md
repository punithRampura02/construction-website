# Construction Website - Flask + Supabase

## 1. Create a virtual environment

Windows:
```bash
python -m venv venv
venv\Scripts\activate
```

## 2. Install packages

```bash
pip install -r requirements.txt
```

## 3. Configure Supabase

Open `.env` and replace `DATABASE_URL` with the PostgreSQL connection string from:

Supabase -> Connect -> Session pooler

Also change `SECRET_KEY`.

## 4. Create the database tables

The `construction` table must contain:
- id
- project_name
- location
- description
- project_type
- status
- area_sqft
- cost_per_sqft
- total_cost
- image_url

The `users` table must contain:
- id
- username
- password_hash

## 5. Create the first admin user

Run:

```bash
flask --app app create-admin
```

Enter your admin username and password.

## 6. Start the website

```bash
python app.py
```

Open:

http://127.0.0.1:5000

## Important

Never upload `.env` to GitHub. It contains your database credentials.
