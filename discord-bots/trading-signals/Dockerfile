FROM python:3.11-slim
WORKDIR /app
COPY discord-bots/trading-signals/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY discord-bots/trading-signals/ .
CMD ["python", "bot.py"]
