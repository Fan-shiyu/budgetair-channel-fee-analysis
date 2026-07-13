# BudgetAir channel-fee MCP server (HTTP transport).
# Small data files are baked in; the 30MB order CSV is NOT needed at runtime
# (segment_detail reads the ~3.6MB parquet built by prepare_mcp_data.py).
FROM python:3.12-slim

# chromium is required by kaleido (>=1.0) to render chart PNGs
RUN apt-get update && apt-get install -y --no-install-recommends \
        chromium ca-certificates fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# code
COPY core.py ./
COPY mcp_server ./mcp_server

# only the small data files the server actually reads
COPY data/outputs/impact_summary.csv        ./data/outputs/impact_summary.csv
COPY data/outputs/app_data                  ./data/outputs/app_data
COPY data/outputs/mcp_data                   ./data/outputs/mcp_data

ENV MCP_TRANSPORT=http \
    HOST=0.0.0.0 \
    PORT=8080 \
    PYTHONUNBUFFERED=1

EXPOSE 8080

# The server runs verify_numbers() at startup and refuses to boot on drifted data.
CMD ["python", "-m", "mcp_server.server"]
