# One image with both runtimes: the Python agent + Streamlit UI starts A's .NET MCP server as a subprocess (stdio).
# Build context = repository root:  docker build -f deploy/Dockerfile .

# ---- 1. build A's C# MCP server -------------------------------------------------------------
FROM mcr.microsoft.com/dotnet/sdk:10.0 AS server-build
WORKDIR /src
COPY contracts/ contracts/
COPY server/ server/
RUN dotnet publish server/SupportServer/SupportServer.csproj -c Release -o /out/server

# ---- 2. runtime: .NET runtime + Python ------------------------------------------------------
FROM mcr.microsoft.com/dotnet/runtime:10.0
RUN apt-get update \
 && apt-get install -y --no-install-recommends python3 python3-venv \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
ENV VIRTUAL_ENV=/opt/venv PATH=/opt/venv/bin:$PATH PYTHONUNBUFFERED=1
COPY agent/requirements.txt agent/requirements.txt
RUN python3 -m venv $VIRTUAL_ENV && pip install --no-cache-dir -r agent/requirements.txt

# The server finds the repo root by the contracts/ folder, so keep the repo layout.
COPY contracts/ contracts/
COPY data/ data/
COPY agent/ agent/
COPY deploy/start.sh deploy/start.sh
COPY --from=server-build /out/server server/bin/

ENV MCP_SERVER_COMMAND="dotnet server/bin/SupportServer.dll" \
    DEMO_NOW=2026-10-31T12:00:00Z \
    LOGGING_CONSOLE_LEVEL=INFO
EXPOSE 8501
CMD ["bash", "deploy/start.sh"]
