FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

WORKDIR /app

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

COPY run.py /app/run.py
COPY backend /app/backend
COPY frontend /app/frontend

EXPOSE 8080

CMD ["python", "run.py", "--production", "--host", "0.0.0.0", "--no-reload"]
