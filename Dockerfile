# Dockerfile
# Production image for Azure Container Apps.
#
# Tailwind's compiled static/css/output.css is committed to the repo and
# copied in as-is — Node isn't installed in this image, so there's no
# `npm run tailwind:build` step here. Rebuild and commit output.css
# locally (see package.json) before deploying any CSS change.

FROM python:3.14-slim

# Unbuffered stdout/stderr so logs show up immediately in Container Apps'
# log stream instead of sitting in a buffer. No .pyc files since the
# container is rebuilt on every deploy anyway.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chmod +x entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]
