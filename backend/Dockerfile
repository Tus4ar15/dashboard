# Use an official Python runtime as a parent image
FROM python:3.12

# Set the working directory in the container
WORKDIR /workspace

# Copy the requirements file and install Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy the current directory contents into the container at /workspace
COPY . .

# Expose the port the app runs on
EXPOSE 5000

# Define environment variable
ENV FLASK_APP=main.py

# Run the command to start the Flask app
CMD ["flask", "run", "--host=0.0.0.0", "--port=5000"]
