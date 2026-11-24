"""Punto de entrada.

Local:       python wsgi.py               -> http://localhost:8000
Producción:  gunicorn wsgi:app            (ver Dockerfile)
"""
import os

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)), debug=True)
