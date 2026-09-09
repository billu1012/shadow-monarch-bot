FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create data and agent_state directories
RUN mkdir -p /app/data /app/agent_state

# Expose the two-way listener API port
EXPOSE 8080

CMD ["python", "shadow_monarch_bot.py"]
