FROM python:3.11-slim
WORKDIR /app

COPY python-stock-backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY python-stock-backend/app.py /app/app.py

EXPOSE 8000
CMD ["python", "app.py"]
