"""WSGI entry-point for production servers (gunicorn, uWSGI).

Usage:
    gunicorn -w 4 -b 0.0.0.0:5000 wsgi:app
"""
from app import create_app

app = create_app()

if __name__ == "__main__":
    # Convenience: `python wsgi.py` boots the dev server too.
    app.run(host="0.0.0.0", port=5000, debug=app.config.get("DEBUG", False))
