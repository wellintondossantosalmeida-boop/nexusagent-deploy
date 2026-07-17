FROM python:3.12-slim

WORKDIR /opt/render/project/src

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc python3-dev && \
    rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 render && \
    mkdir -p /tmp/nexusagent && \
    chown -R render:render /tmp/nexusagent && \
    chown -R render:render /opt/render/project/src

USER render

COPY --chown=render:render requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=render:render . .

ENV AGENT_DATA_DIR=/tmp/nexusagent
ENV PYTHONUNBUFFERED=1

EXPOSE 10000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "10000"]
