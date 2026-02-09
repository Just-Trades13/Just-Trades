FROM python:3.11-slim
WORKDIR /app
COPY discord-bots/ecosystem/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY discord-bots/ecosystem/ .
CMD ["python", "run_bots.py"]
