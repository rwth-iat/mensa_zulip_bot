FROM python:3.11-slim

RUN echo "Installing git to clone mensa-aachen..."
RUN apt-get update && apt-get install -y git && apt-get clean

RUN echo "Preparing container files..."
WORKDIR /

COPY requirements.txt .
COPY config.ini .

RUN echo "Installing requirements..."
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]
