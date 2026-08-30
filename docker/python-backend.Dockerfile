FROM python:3.11-slim
WORKDIR /app

# AI Sheet의 LEAN 백테스트 버튼이 호스트 Docker 데몬에 `docker` CLI로 직접
# 명령을 보낸다(Docker-outside-of-Docker). 데몬은 필요 없고 클라이언트만
# 필요하므로 docker-cli만 설치한다(docker.io는 불필요한 dockerd까지 끌고 온다).
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends docker-cli \
    && rm -rf /var/lib/apt/lists/*

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
