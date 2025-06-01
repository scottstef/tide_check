# my_tide_app/Dockerfile

# Use an official Python runtime as a parent image
# python:3.9-slim-buster provides a lean Debian-based Python environment
FROM python:3.9-slim-buster

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the working directory
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
# --no-cache-dir: Don't store package build artifacts in cache
# -r: Install from requirements file
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire application code into the container
# The .dockerignore file (optional) can be used to exclude files like .git, .env
COPY . .

# Expose port 5000 which the app will run on
EXPOSE 5000

# Command to run the application using Gunicorn
# gunicorn: The WSGI HTTP server
# -w 4: Run with 4 worker processes (adjust based on CPU cores)
# -b 0.0.0.0:5000: Bind to all network interfaces on port 5000
# app:app: The 'app' module (app.py) and the 'app' Flask instance within it
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "app:app"]

