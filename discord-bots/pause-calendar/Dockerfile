FROM python:3.11-slim
WORKDIR /app
COPY discord-bots/pause-calendar/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY discord-bots/pause-calendar/ .
CMD ["python", "bot.py"]
