FROM python:3.11-slim
WORKDIR /workspace
COPY requirements-core.txt requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt
COPY . .
RUN useradd --create-home --uid 10001 quant && mkdir -p /workspace/data/runtime && chown -R quant:quant /workspace
USER quant
ENV PYTHONUNBUFFERED=1 DATA_DIR=/workspace/data/runtime
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
