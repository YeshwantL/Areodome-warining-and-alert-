# Base Image
FROM python:3.9-slim

# Set Working Directory
WORKDIR /app

# Install System Dependencies (if any required by libraries, though slim usually suffices for basic python)
# We might need build essentials for some libraries if wheels aren't valid, but let's try pure slim first.
# psycopg2-binary usually helps avoid libpq-dev

# Copy Requirements
COPY requirements.txt .

# Install Python Dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy Project Files
COPY . .

# Set Environment Variables
# Adjusted for backend directory structure:
# Root is /app (which contains app, routers, etc.)
# app is /app/app
# database is /app/app/database
ENV PYTHONPATH="/app:/app/app:/app/app/database"
# Database file is now at /app/sql_app.db (persisted via volume)
ENV DATABASE_URL="sqlite:////app/sql_app.db"

# Expose Port
EXPOSE 8000

# Run Application
# main.py is in app/main.py relative to WORKDIR /app
CMD ["python", "app/main.py"]
