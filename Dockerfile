FROM python:3.12-slim
RUN apt-get update && apt-get -y install cron vim dos2unix wget
WORKDIR /app

COPY crontab /etc/cron.d/crontab
RUN dos2unix /etc/cron.d/crontab /etc/cron.d/crontab
RUN chmod 0644 /etc/cron.d/crontab
RUN touch /var/log/cron.log
RUN /usr/bin/crontab /etc/cron.d/crontab

COPY requirements.txt /app/requirements.txt
ADD components /app/components
COPY main.py /app/main.py
RUN pip install -r /app/requirements.txt

# run crond as main process of container
CMD ["cron", "-f"]