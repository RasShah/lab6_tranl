FROM python:3.13-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends bison flex gcc libc6-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . .
RUN python scripts/build_native.py

ENTRYPOINT ["python", "main.py"]
CMD ["examples/valid/basic.mini"]
