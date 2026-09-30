"""WSGI entrypoint: gunicorn -c deploy/gunicorn.conf.py wsgi:app"""
from veda.app import create_app

app = create_app()
