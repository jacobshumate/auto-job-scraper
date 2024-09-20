FROM python:3.12-slim

# Add a non-root user
RUN useradd -ms /bin/bash scraperuser

# Switch to non-root user, set the working directory and pythonpath
USER scraperuser
WORKDIR /home/scraperuser/app
ENV PYTHONPATH="/home/scraperuser/.local/lib/python3.12/site-packages:$PYTHONPATH"

# Copy application files as non-root user
COPY requirements.txt app/main.py cron/run_scraper.sh ./
ADD app/components ./components

# Install Python packages as non-root user
RUN pip install --no-cache-dir -r requirements.txt

# Switch to root to set up packages and cron jobs
USER root

# Install necessary packages and clean up
RUN apt-get update && \
    apt-get -y install cron dos2unix && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set up cron jobs
COPY cron/crontab /etc/cron.d/crontab
RUN dos2unix /etc/cron.d/crontab && \
    chmod 0644 /etc/cron.d/crontab && \
    touch /var/log/cron.log && \
    /usr/bin/crontab /etc/cron.d/crontab

# Set the CMD to run cron as root
CMD ["cron", "-f"]