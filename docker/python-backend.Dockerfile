# syntax=docker/dockerfile:1
FROM python:3.12-slim
WORKDIR /app

# AI Sheet의 LEAN 백테스트 버튼이 호스트 Docker 데몬에 `docker` CLI로 직접
# 명령을 보낸다(Docker-outside-of-Docker). 데몬은 필요 없고 클라이언트만
# 필요하므로 docker-cli만 설치한다(docker.io는 불필요한 dockerd까지 끌고 온다).
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends docker-cli \
    && rm -rf /var/lib/apt/lists/*

# 의존성은 uv + 잠금 파일(uv.lock)로 재현 가능하게 설치한다.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/app/.venv
COPY python-stock-backend/pyproject.toml python-stock-backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
ENV PATH="/app/.venv/bin:$PATH"

# fastembed 임베딩 모델(paraphrase-multilingual-MiniLM-L12-v2, ~118MB)을 미리 내려받아
# 컨테이너가 런타임 네트워크 없이도 즉시 RAG 검색을 시작할 수 있게 한다.
RUN python -c "from fastembed import TextEmbedding; TextEmbedding('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'); print('fastembed model ready')"

COPY python-stock-backend/app ./app

EXPOSE 8200
# KIS 토큰·호출 제한기는 프로세스 메모리에서 공유하므로 worker는 1개로 둔다.
# 동기 라우트는 Starlette 스레드풀에서 실행되어 요청 동시성을 처리한다.
# 다중 worker 확장은 Redis 기반 제한기로 전환한 뒤 적용해야 한다.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8200", "--workers", "1", "--proxy-headers", "--forwarded-allow-ips", "*"]
