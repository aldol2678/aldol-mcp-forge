FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY ui_core ./ui_core
RUN useradd --uid 10001 --create-home app
USER app
CMD ["python", "-m", "ui_core.http_server"]
