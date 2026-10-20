FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends nodejs && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd --uid 10001 --create-home gameops
COPY server.py service.py worker.py ./
COPY scripts ./scripts
RUN mkdir /app/reports && chown gameops:gameops /app/reports
USER 10001:10001
ENV GAME_OPS_REPORT_ROOT=/app/reports PYTHONDONTWRITEBYTECODE=1
# No Chromium or Playwright in remote image; HTTP blocks browser calls regardless of env flags.
CMD ["python", "server.py", "--http"]
