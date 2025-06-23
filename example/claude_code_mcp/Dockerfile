FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y curl
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"
WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync

COPY . ./
EXPOSE 8000
CMD ["uv", "run", "python", "main.py"]