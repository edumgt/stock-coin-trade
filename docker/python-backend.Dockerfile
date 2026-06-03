FROM python:3.11-slim
WORKDIR /app

COPY python-stock-backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY python-stock-backend/app.py .

EXPOSE 8200
CMD ["python", "app.py"]
