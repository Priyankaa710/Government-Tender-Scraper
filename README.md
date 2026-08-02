# Tender Trail

This repository contains the **Tender Trail** application — an AI-assisted government tender management system that automates the collection, tracking, and alerting of tenders scraped from multiple government procurement portals.

**Live Demo:** [https://government-tender-scraper.onrender.com/](https://government-tender-scraper.onrender.com/)

## Project Structure

- `tender_trail/` - Django project settings, root URLs, WSGI/ASGI entry points.
- `tenders/` - Core app: tender models, views, forms, REST API (serializers/api_views), analytics, admin.
- `users/` - User registration, authentication, and profile-related views/APIs.
- `scraper/` - Multi-threaded scraper engine (`scrapers.py`, `parser.py`, `threading_utils.py`), alert engine, and management commands (`run_scraper`, `send_alerts`, `seed_data`).
- `templates/` - Django HTML templates (`tenders/`, `users/`, `base.html`).
- `static/` - CSS, JS, and image assets served via Whitenoise.
- `manage.py` - Django's command-line utility.
- `Dockerfile` / `docker-compose.yml` - Container setup for the web app, scraper worker, and MongoDB.

## Setup Instructions

### Backend (Django)

1. Navigate to the project folder:
   ```
   cd tender_trail
   ```
2. Create a virtual environment and install dependencies:
   ```
   python -m venv venv
   venv\Scripts\activate   # Windows
   source venv/bin/activate   # macOS/Linux
   pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env` and configure values like `DJANGO_SECRET_KEY`, `MONGO_HOST`, `MONGO_DB_NAME`, and `EMAIL_HOST` settings.
4. Apply migrations:
   ```
   python manage.py migrate
   ```
5. (Optional) Seed sample tender data:
   ```
   python manage.py seed_data
   ```
6. Run the server:
   ```
   python manage.py runserver
   ```
7. The app will be available at `http://127.0.0.1:8000`.

### Frontend

The frontend is not a separate application — it's server-rendered directly by Django using HTML templates (`templates/`) styled with Bootstrap, CSS, and vanilla JS (`static/`). No separate install or build step is required; it runs automatically with the backend server above.

### Scraper & Alert Engine

- Run the scraper once: `python manage.py run_scraper`
- Run the scraper continuously (respecting `SCRAPER_INTERVAL_HOURS`): `python manage.py run_scraper --loop`
- Send deadline reminder emails: `python manage.py send_alerts`

## Building for Production

- No separate frontend build step is needed since templates are rendered server-side.
- Collect static files for Whitenoise:
  ```
  python manage.py collectstatic --noinput
  ```
- Set `DJANGO_DEBUG=False` and configure `DJANGO_ALLOWED_HOSTS` in `.env` before deploying.
- Serve with a production WSGI server:
  ```
  gunicorn tender_trail.wsgi:application --bind 0.0.0.0:8000 --workers 3
  ```

## Deployment

Tender Trail is deployed on Render and is live at **[https://government-tender-scraper.onrender.com/](https://government-tender-scraper.onrender.com/)**.

The project also ships with Docker support for self-hosting:

1. Copy `.env.example` to `.env` and fill in your configuration.
2. Build and start all services (web app, scraper worker, and MongoDB):
   ```
   docker-compose up --build
   ```
3. The `web` service runs migrations, collects static files, and starts Gunicorn automatically; the `scraper` service runs continuously in the background.
4. Visit `http://localhost:8000` to confirm the app is running.

For platforms like Render, Railway, or Heroku: point the build at the included `Dockerfile` (or `requirements.txt`), set the environment variables from `.env.example`, and use `gunicorn tender_trail.wsgi:application` as the start command. Make sure a MongoDB instance (e.g., MongoDB Atlas) is reachable via the `MONGO_*` variables.

## Contributing

1. Fork the repository.
2. Create a feature branch: `git checkout -b feature-name`.
3. Make your changes and commit them with clear messages.
4. Push to your fork and create a pull request.

## License

This project is open source. Replace with your chosen license.
