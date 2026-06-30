FROM python:3.11-slim
WORKDIR /app

COPY python-stock-backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download fastembed model (intfloat/multilingual-e5-small, ~118MB)
# so the container starts instantly without network access at runtime
RUN python3 -c "\
from qdrant_client import QdrantClient; \
c = QdrantClient(':memory:'); \
c.set_model('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'); \
c.add('warmup', documents=['warmup']); \
print('fastembed model ready')"

COPY python-stock-backend/*.py .

EXPOSE 8200
CMD ["python", "app.py"]
