FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
COPY src/ingestion/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY src/ingestion/ /app/
COPY sql/w5_ingestion.sql /app/w5_ingestion.sql
COPY sql/w5_demo_assets.sql /app/w5_demo_assets.sql
COPY docs/data_contracts/schemas/ /app/schemas/
CMD ["python", "worker.py"]
