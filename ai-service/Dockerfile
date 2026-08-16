FROM python:3.10-slim-bookworm
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
# Keep the installer deterministic enough to normalize modern wheel metadata;
# the older pip bundled in moving `slim` images rejected `typing_extensions`.
RUN python -m pip install --no-cache-dir --upgrade pip==25.1.1
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu \
    torch==2.5.1 torchvision==0.20.1
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN useradd -r -u 10001 dermai && chown -R dermai:dermai /app
USER dermai
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
