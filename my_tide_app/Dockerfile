# Use a slim Python image as a base
FROM python:3.12-slim-buster

# Set the working directory inside the container
WORKDIR /app

# had to upgrade to build essentials to get it to run rather than a stripped down python version
# numpys and pandas can be chunky
RUN apt-get update && \
    apt-get install -y build-essential python3-dev && \
    rm -rf /var/lib/apt/lists/*

# Copy the requirements file into the container
COPY requirements.txt .

# Install Python dependencies from the requirements file
RUN pip install --no-cache-dir -r requirements.txt


COPY . .


ENV FLASK_APP=app.py

# Expose the port your Flask app runs on
EXPOSE 5000

# Command to run the application using Gunicorn
# Adjust workers as needed based on your Lightsail instance size
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]
