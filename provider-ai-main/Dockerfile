# syntax=docker/dockerfile:1

ARG PYTHON_VERSION=3.12-slim
FROM python:${PYTHON_VERSION}

# 1) Install system packages required by psutil (and any others)
RUN apt-get update && \
    apt-get install -y gcc python3-dev && \
    rm -rf /var/lib/apt/lists/*

# 2) Use /app as the working directory
WORKDIR /app

# 3) Install Poetry globally (not user-local)
RUN pip install --no-cache-dir poetry

# 4) Copy in your pyproject.toml and poetry.lock first for dependency caching
COPY pyproject.toml poetry.lock ./

# 5) Install dependencies
RUN poetry install --no-root --no-interaction --no-ansi

# 6) Copy the rest of your code into /app
COPY . .
WORKDIR /app/agent
# 7) Final entrypoint
ENTRYPOINT ["poetry", "run", "python", "agent.py"]
CMD ["start"]
