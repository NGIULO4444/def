FROM python:3.11-slim

# Crea directory app
WORKDIR /app

# Copia files necessari
COPY vnc_server_cloud.py .
COPY vnc_protocol.py .
COPY requirements-cloud.txt .

# Installa dipendenze
RUN pip install -r requirements-cloud.txt

# Esponi porta (Railway la assegna dinamicamente)
EXPOSE $PORT

# Avvia server
CMD ["python", "vnc_server_cloud.py"] 