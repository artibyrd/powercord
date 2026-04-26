# --- Build Stage ---
# Use an official Python runtime as a parent image
FROM python:3.12-slim-bookworm as builder

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    POETRY_VIRTUALENVS_CREATE=1 \
    POETRY_CACHE_DIR=/tmp/poetry_cache

# Set the working directory
WORKDIR /app

# Install poetry
RUN pip install --no-cache-dir poetry

# Copy only dependency files to leverage Docker cache
COPY pyproject.toml poetry.lock ./

# Install dependencies without installing the project itself
RUN poetry install --no-root --without dev,test

# Copy only what's needed for the application to keep the build context clean
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini .
COPY .example.env ./.example.env

# Install the project itself
RUN poetry install --without dev,test


# --- Final Stage ---
FROM python:3.12-slim-bookworm

WORKDIR /app

# Install system dependencies for Nginx, Supervisor, PostgreSQL, and OpenSSL
RUN apt-get update && apt-get install -y --no-install-recommends \
    nginx \
    supervisor \
    postgresql \
    openssl \
    && rm -rf /var/lib/apt/lists/*

# Copy the virtual environment and application code from the builder stage
COPY --from=builder /app/.venv ./.venv
COPY --from=builder /app/app ./app
COPY --from=builder /app/alembic ./alembic
COPY --from=builder /app/alembic.ini .
COPY --from=builder /app/.example.env ./.example.env

# Add the virtual environment to the PATH
ENV PATH="/app/.venv/bin:$PATH"

# Copy configuration files
COPY nginx.conf /etc/nginx/nginx.conf
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf
COPY start.sh /start.sh
RUN chmod +x /start.sh

# Expose the ports Nginx will run on
EXPOSE 80
EXPOSE 443

# Define the volume for PostgreSQL data
VOLUME /var/lib/postgresql/data

# Start our entrypoint script, which will in turn start supervisord
CMD ["/start.sh"]
