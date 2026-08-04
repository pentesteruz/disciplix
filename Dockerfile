# Use official Python 3.12 image which has build tools (gcc, etc.)
FROM python:3.12

# Install Node.js 20
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements & install Python dependencies (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all application files
COPY . .

# Build the Next.js frontend
WORKDIR /app/web2
RUN npm ci || npm install
RUN npm run build

# Return to root directory
WORKDIR /app

# Create and switch to non-root user for security
RUN useradd -m -r botuser && chown -R botuser /app
USER botuser

# Run the bot
CMD ["python", "bot.py"]
