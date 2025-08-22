import os
import sys
import logging
import traceback

import time
import threading
import shutil
from functools import wraps
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


from flask import Flask, send_from_directory, render_template, make_response, redirect, request, abort, jsonify, current_app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

from flask_cors import CORS, cross_origin
from flask_limiter.errors import RateLimitExceeded
from src.celery_app import celery as celery_app
from src.models.user import db, APILog # Import APILog
from src.models.metrics import JobMetric, DailyMetric
from src.config import DevelopmentConfig, ProductionConfig
import requests
import smtplib
from email.message import EmailMessage
from src.utils.limiter import limiter




def configure_celery(app, celery_instance):
    celery_instance.conf.update(app.config)
    
    # Apply SSL fixes directly
    def fix_redis_ssl_url(url):
        """Add SSL cert requirements to rediss:// URLs if missing"""
        if url and url.startswith('rediss://') and 'ssl_cert_reqs' not in url:
            # Add CERT_NONE for managed Redis services like Upstash
            separator = '&' if '?' in url else '?'
            return f"{url}{separator}ssl_cert_reqs=CERT_NONE"
        return url
    
    # Get and fix Redis URLs
    redis_url = os.environ.get('REDIS_URL')
    broker_url = os.environ.get('CELERY_BROKER_URL') or redis_url or 'redis://localhost:6379/0'
    backend_url = os.environ.get('CELERY_RESULT_BACKEND') or redis_url or 'redis://localhost:6379/0'
    
    # Apply SSL fixes and set configuration
    celery_instance.conf.broker_url = fix_redis_ssl_url(broker_url)
    celery_instance.conf.result_backend = fix_redis_ssl_url(backend_url)
    
    # Debug logging
    logging.debug(
        "[Flask Debug] Celery broker_url: %s", celery_instance.conf.broker_url
    )
    logging.debug(
        "[Flask Debug] Celery result_backend: %s",
        celery_instance.conf.result_backend,
    )
    
    # Celery config is updated from Flask config. Keys like CELERY_BROKER_URL
    # are automatically mapped to broker_url. The line below was incorrect
    # as it was trying to read a lowercase key from Flask's config and overwriting the setting.
    # celery_instance.conf.result_backend = app.config.get('result_backend')

    class ContextTask(celery_instance.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return super().__call__(*args, **kwargs)
    celery_instance.Task = ContextTask

def admin_required(f):
    """Verify that the request contains a valid admin token."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        token = current_app.config.get('ADMIN_TOKEN')
        auth = request.headers.get('Authorization', '')
        if not token or not auth.startswith('Bearer ') or auth.split(' ', 1)[1] != token:
            abort(401)
        return f(*args, **kwargs)
    return wrapper

def create_app():
    app = Flask(__name__, 
                static_folder=os.path.join(os.path.dirname(__file__), 'static'),
                template_folder=os.path.join(os.path.dirname(__file__), 'static'))
    
    config_class = ProductionConfig if os.environ.get('FLASK_ENV') == 'production' else DevelopmentConfig
    app.config.from_object(config_class)
    app.config['ADMIN_TOKEN'] = os.environ.get('ADMIN_TOKEN')

    # Ensure the upload folder exists
    upload_folder = app.config.get('UPLOAD_FOLDER')
    if upload_folder:
        os.makedirs(upload_folder, exist_ok=True)

    # Initialize extensions
    CORS(app, resources={r"/api/*": {"origins": app.config['CORS_ORIGINS']}})
    db.init_app(app)
    app.config.setdefault("RATELIMIT_HEADERS_ENABLED", True)
    limiter.init_app(app)

    # Configure Celery with the Flask app context BEFORE importing blueprints/tasks
    configure_celery(app, celery_app)
    logging.debug(
        "[Flask Debug] Celery broker_url: %s", celery_app.conf.broker_url
    )
    logging.debug(
        "[Flask Debug] Celery result_backend: %s",
        celery_app.conf.result_backend,
    )
    app.celery = celery_app

    # Import tasks now that Celery has been configured so tasks can register safely
    import src.tasks  # noqa: F401
    import src.tasks_cleanup  # noqa: F401
    # Import blueprints and tasks AFTER Celery is configured
    from src.routes.gif import gif_bp
    # from src.routes.user import user_bp  # Disabled for MVP
    app.register_blueprint(gif_bp, url_prefix='/api')
    # app.register_blueprint(user_bp, url_prefix='/api')

    # Import SEO pages data
    from src.seo_pages import seo_pages, get_related_pages

    with app.app_context():
        # Create database tables if they don't exist
        db.create_all()

    @app.errorhandler(RateLimitExceeded)
    def handle_rate_limit(e):
        return jsonify({"error": "Rate limit exceeded", "limit": str(e.description)}), 429

    # -------------------- Admin routes (defined BEFORE catch-all) --------------------
    @app.route('/admin/indexnow/submit', methods=['POST'])
    @admin_required
    def admin_indexnow_submit():
        """Submit provided or all known URLs to IndexNow. Body JSON: {"urls": [...], "dry_run": bool}"""
        try:
            data = request.get_json(silent=True) or {}
            urls = data.get('urls')
            dry_run = bool(data.get('dry_run'))
            base_url = 'https://easygifmaker.com'
            from src.seo_pages import seo_pages as _seo_pages
            core = [
                '', 'video-to-gif','gif-maker','resize','crop','optimize','add-text','reverse','about','help','contact','privacy-policy','terms','blog'
            ]
            if not urls:
                urls = [base_url + ('/' + u if u else '/') for u in core]
                urls += [f"{base_url}/{p['category']}/{p['slug']}" for p in _seo_pages]
            # Deduplicate
            seen=set(); dedup=[]
            for u in urls:
                if u not in seen:
                    seen.add(u); dedup.append(u)
            urls=dedup
            if dry_run:
                return {'status':'dry_run','count':len(urls),'urls':urls[:50]}
            from src.utils.indexnow import get_indexnow_client
            client = get_indexnow_client()
            success = client.submit_urls(urls)
            return {'status': 'ok' if success else 'partial', 'count': len(urls), 'endpoints': getattr(client, "last_results", [])}
        except Exception as e:
            return {'error': str(e)}, 500

    @app.route('/admin/indexnow/sitemap', methods=['POST'])
    @admin_required
    def admin_indexnow_sitemap():
        """Submit sitemap.xml URL to IndexNow"""
        try:
            sitemap_url = 'https://easygifmaker.com/sitemap.xml'
            from src.utils.indexnow import notify_url_change
            success = notify_url_change(sitemap_url)
            return {'status':'ok' if success else 'partial', 'url': sitemap_url}
        except Exception as e:
            return {'error': str(e)}, 500



    @app.route('/admin/usage')
    @admin_required
    def view_usage():
        logs = APILog.query.order_by(APILog.timestamp.desc()).limit(100).all()
        html = "<h2>API Usage Log</h2><table border='1'><tr><th>Time</th><th>IP</th><th>Path</th><th>Method</th><th>User-Agent</th></tr>"
        for log in logs:
            html += f"<tr><td>{log.timestamp}</td><td>{log.ip}</td><td>{log.path}</td><td>{log.method}</td><td>{log.user_agent}</td></tr>"
        html += "</table>"
        return html

    @app.route('/admin/job-metrics')
    @admin_required
    def view_job_metrics():
        rows = JobMetric.query.order_by(JobMetric.created_at.desc()).limit(200).all()
        html = "<h2>Job Metrics</h2><table border='1'>"
        html += "<tr><th>Time</th><th>Tool</th><th>Status</th><th>Task ID</th><th>In WxH</th><th>Frames</th><th>In Size</th><th>Out Size</th><th>Time (ms)</th><th>Options</th><th>Error</th></tr>"
        for r in rows:
            wh = f"{r.input_width}x{r.input_height}" if r.input_width and r.input_height else "-"
            html += (
                f"<tr><td>{r.created_at}</td><td>{r.tool}</td><td>{r.status}</td><td>{r.task_id}</td><td>{wh}</td><td>{r.input_frames or '-'}"
                f"</td><td>{r.input_size_bytes or '-'}"
                f"</td><td>{r.output_size_bytes or '-'}"
                f"</td><td>{r.processing_time_ms or '-'}"
                f"</td><td>{(r.options or '').replace('<','&lt;').replace('>','&gt;')}</td>"
                f"<td>{(r.error_message or '').replace('<','&lt;').replace('>','&gt;')}</td></tr>"
            )
        html += "</table>"
        return html

    @app.route('/admin/job-metrics/summary')
    @admin_required
    def metrics_summary():
        try:
            import datetime
            hours = int(request.args.get('hours', 24))
            since = datetime.datetime.utcnow() - datetime.timedelta(hours=hours)
            q = JobMetric.query.filter(JobMetric.created_at >= since)
            total = q.count()
            failures = q.filter(JobMetric.status == 'FAILURE').count()
            by_tool = {}
            for row in q.all():
                by_tool[row.tool] = by_tool.get(row.tool, 0) + 1
            # p95 runtime (ms)
            runtimes = [r.processing_time_ms for r in q.filter(JobMetric.processing_time_ms.isnot(None)).all()]
            runtimes.sort()
            p95 = runtimes[int(0.95 * (len(runtimes)-1))] if runtimes else None
            return {
                'window_hours': hours,
                'total': total,
                'failures': failures,
                'failure_rate': (failures / total) if total else 0,
                'by_tool': by_tool,
                'p95_processing_time_ms': p95,
            }
        except Exception as e:
            return {'error': str(e)}, 500

    # API-prefixed aliases to avoid SPA catch-all in some deployments
    @app.route('/api/admin/job-metrics/summary')
    @admin_required
    def api_metrics_summary_alias():
        return metrics_summary()

    @app.route('/admin/daily-metrics/rebuild')
    @admin_required
    def rebuild_daily_metrics():
        import datetime
        start = request.args.get('start')  # YYYY-MM-DD
        end = request.args.get('end')      # YYYY-MM-DD
        if not start or not end:
            return {'error': 'start and end (YYYY-MM-DD) are required'}, 400
        start_date = datetime.date.fromisoformat(start)
        end_date = datetime.date.fromisoformat(end)
        day = start_date
        try:
            while day <= end_date:
                next_day = day + datetime.timedelta(days=1)
                rows = JobMetric.query.filter(
                    JobMetric.created_at >= datetime.datetime.combine(day, datetime.time.min),
                    JobMetric.created_at < datetime.datetime.combine(next_day, datetime.time.min)
                ).all()
                by_tool = {}
                for r in rows:
                    by_tool.setdefault(r.tool, []).append(r)
                for tool, items in by_tool.items():
                    total = len(items)
                    failures = sum(1 for i in items if i.status == 'FAILURE')
                    runtimes = [i.processing_time_ms for i in items if i.processing_time_ms is not None]
                    runtimes.sort()
                    p95 = runtimes[int(0.95 * (len(runtimes)-1))] if runtimes else None
                    avg = int(sum(runtimes)/len(runtimes)) if runtimes else None
                    existing = DailyMetric.query.filter_by(day=day, tool=tool).first()
                    if not existing:
                        existing = DailyMetric(day=day, tool=tool, total=total, failures=failures, p95_ms=p95, avg_ms=avg)
                        db.session.add(existing)
                    else:
                        existing.total = total
                        existing.failures = failures
                        existing.p95_ms = p95
                        existing.avg_ms = avg
                db.session.commit()
                day = next_day
            return {'status': 'ok'}
        except Exception as e:
            db.session.rollback()
            return {'error': str(e)}, 500

    @app.route('/api/admin/daily-metrics/rebuild')
    @admin_required
    def api_rebuild_daily_metrics_alias():
        return rebuild_daily_metrics()

    @app.route('/admin/daily-metrics')
    @admin_required
    def list_daily_metrics():
        tool = request.args.get('tool')
        q = DailyMetric.query
        if tool:
            q = q.filter(DailyMetric.tool == tool)
        rows = q.order_by(DailyMetric.day.desc()).limit(60).all()
        return {'items': [r.to_dict() for r in rows]}

    @app.route('/api/admin/daily-metrics')
    @admin_required
    def api_list_daily_metrics_alias():
        return list_daily_metrics()

    @app.route('/api/admin/job-metrics')
    @admin_required
    def api_view_job_metrics_alias():
        return view_job_metrics()
    # -------------------------------------------------------------------------------

    @app.before_request
    def log_ai_api_usage():
        if request.path.startswith('/api/ai/'):
            log = APILog(
                ip=request.remote_addr,
                user_agent=request.headers.get('User-Agent', 'unknown'),
                path=request.path,
                method=request.method
            )
            db.session.add(log)
            db.session.commit()

    @app.post('/api/contact')
    def api_contact():
        try:
            data = request.get_json(silent=True) or {}
            name = (data.get('name') or '').strip()
            email = (data.get('email') or '').strip()
            message = (data.get('message') or '').strip()
            if not name or not email or not message:
                return {'error': 'name, email, and message are required'}, 400
            if len(message) > 5000:
                return {'error': 'message too long'}, 400
            # Basic email sanity
            if '@' not in email or '.' not in email:
                return {'error': 'invalid email'}, 400
            # Log meta
            logging.info(f"Contact form submission from {email}: name={name}, len={len(message)}")

            delivered = False

            # 0) Gmail SMTP (or other SMTP) if configured
            smtp_host = os.environ.get('SMTP_HOST', 'smtp.gmail.com')
            smtp_port = int(os.environ.get('SMTP_PORT', '587'))
            smtp_user = os.environ.get('SMTP_USER')
            smtp_pass = os.environ.get('SMTP_PASS')
            to_email = os.environ.get('CONTACT_TO_EMAIL') or os.environ.get('OWNER_EMAIL')
            from_email = os.environ.get('CONTACT_FROM_EMAIL') or smtp_user
            if smtp_user and smtp_pass and to_email and from_email:
                try:
                    msg = EmailMessage()
                    msg['Subject'] = f"[EGM Contact] Message from {name}"
                    msg['From'] = from_email
                    msg['To'] = to_email
                    # Let you hit Reply and respond directly to the user
                    msg['Reply-To'] = email
                    body = (
                        f"Name: {name}\n"
                        f"Email: {email}\n\n"
                        f"Message:\n{message}\n"
                    )
                    msg.set_content(body)

                    with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
                        server.ehlo()
                        server.starttls()
                        server.login(smtp_user, smtp_pass)
                        server.send_message(msg)
                        delivered = True
                except Exception as e:
                    logging.error(f"SMTP send error: {e}")

            # 1) Send email via SendGrid if configured
            sendgrid_key = os.environ.get('SENDGRID_API_KEY')
            sendgrid_to = os.environ.get('CONTACT_TO_EMAIL') or os.environ.get('OWNER_EMAIL')
            sendgrid_from = os.environ.get('CONTACT_FROM_EMAIL') or (sendgrid_to or 'no-reply@easygifmaker.com')
            if not delivered and sendgrid_key and sendgrid_to:
                try:
                    sg_payload = {
                        "personalizations": [
                            {"to": [{"email": sendgrid_to}], "subject": f"[EGM Contact] Message from {name}"}
                        ],
                        "from": {"email": sendgrid_from},
                        "content": [
                            {"type": "text/plain", "value": f"Name: {name}\nEmail: {email}\n\nMessage:\n{message}"}
                        ]
                    }
                    r = requests.post(
                        'https://api.sendgrid.com/v3/mail/send',
                        headers={
                            'Authorization': f'Bearer {sendgrid_key}',
                            'Content-Type': 'application/json'
                        }, json=sg_payload, timeout=10
                    )
                    if 200 <= r.status_code < 300:
                        delivered = True
                    else:
                        logging.warning(f"SendGrid response {r.status_code}: {r.text}")
                except Exception as e:
                    logging.error(f"SendGrid error: {e}")

            # 2) Post to Slack webhook if configured
            slack_webhook = os.environ.get('SLACK_WEBHOOK_URL')
            if not delivered and slack_webhook:
                try:
                    text = f"*EGM Contact*\n*From:* {name} <{email}>\n*Message:*\n{message}"
                    r = requests.post(slack_webhook, json={"text": text}, timeout=10)
                    if 200 <= r.status_code < 300:
                        delivered = True
                    else:
                        logging.warning(f"Slack webhook response {r.status_code}: {r.text}")
                except Exception as e:
                    logging.error(f"Slack webhook error: {e}")

            # If nothing configured, we still return ok after logging meta
            return ({'status': 'ok', 'delivered': delivered}, 200)
        except Exception as e:
            logging.error(f"/api/contact error: {e}")
            return {'error': 'internal error'}, 500

    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def serve(path):
        static_folder_path = app.static_folder
        if static_folder_path is None:
            return "Static folder not configured", 404

        # Check if this is an SEO page route
        if path and '/' in path:
            category, slug = path.split('/', 1)
            page = next((p for p in seo_pages if p['slug'] == slug and p['category'] == category), None)
            if page:
                related_pages = get_related_pages(page)
                return render_template('seo_template.html', page=page, related_pages=related_pages)

        # Check if this is a React app route (tools, blog, etc.)
        react_routes = [
            'gif-maker', 'video-to-gif', 'resize', 'crop', 'optimize', 'add-text',
            'blog', 'about', 'contact', 'faq', 'help', 'privacy-policy', 'terms'
        ]
        
        if path in react_routes or path.startswith('blog/'):
            # Serve React app for tool pages
            index_path = os.path.join(static_folder_path, 'index.html')
            if os.path.exists(index_path):
                return send_from_directory(static_folder_path, 'index.html')
            else:
                return "index.html not found", 404

        # Serve static files
        if path != "" and os.path.exists(os.path.join(static_folder_path, path)):
            return send_from_directory(static_folder_path, path)
        else:
            index_path = os.path.join(static_folder_path, 'index.html')
            if os.path.exists(index_path):
                return send_from_directory(static_folder_path, 'index.html')
            else:
                return "index.html not found", 404

    @app.errorhandler(Exception)
    def handle_exception(e):
        tb_str = traceback.format_exc()
        logging.error(f"Unhandled Exception: {e}\n{tb_str}")
        # In production, you might not want to send the full traceback to the client
        if app.config.get('DEBUG', False):
            return {'error': str(e), 'traceback': tb_str}, 500
        return {'error': 'An internal server error occurred.'}, 500
    
    return app

app = create_app()

@app.route('/sitemap.xml')
def sitemap():
    from flask import Response
    import datetime
    from src.seo_pages import seo_pages
    
    base_url = "https://easygifmaker.com"

    static_urls = [
        base_url + "/",
        base_url + "/reverse",
        base_url + "/about",
        base_url + "/contact",
        base_url + "/faq",
        base_url + "/video-to-gif",
        base_url + "/gif-maker",
        base_url + "/crop",
        base_url + "/optimize",
        base_url + "/add-text",
        base_url + "/resize",
        base_url + "/blog"
    ]

    # Add SEO pages dynamically
    seo_urls = [
        f"{base_url}/{p['category']}/{p['slug']}" for p in seo_pages
    ]

    blog_slugs = [
        "how-to-make-gifs-from-videos",
        "top-5-gif-optimization-tips",
        "ultimate-guide-to-viral-gifs",
        "add-text-to-gifs-guide",
        "master-the-art-of-adding-text-to-gifs",
        "professional-gif-cropping-and-composition-guide",
        "gif-for-business-marketing",
        "gif-accessibility-guide",
        "gif-optimization-techniques",
        "comprehensive-gif-making-guide",
        "complete-guide-to-resize-gif",
        "social-media-gif-strategy",
        "creative-gif-design-tutorial"
    ]
    blog_urls = [f"{base_url}/blog/{slug}" for slug in blog_slugs]

    urls = static_urls + seo_urls + blog_urls

    xml = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    for url in urls:
        xml += f"  <url>\n    <loc>{url}</loc>\n    <lastmod>{datetime.date.today()}</lastmod>\n    <changefreq>weekly</changefreq>\n    <priority>0.7</priority>\n  </url>\n"
    xml += '</urlset>'

    return Response(xml, mimetype='application/xml')

@app.route('/.well-known/ai-plugin.json')
def serve_plugin_manifest():
    response = make_response(send_from_directory('static/.well-known', 'ai-plugin.json'))
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Content-Type'] = 'application/json'
    response.headers['AI-Plugin'] = 'true'
    response.headers['X-AI-Support'] = 'easygifmaker'
    return response

@app.route('/openapi.yaml')
def serve_openapi_spec():
    response = make_response(send_from_directory('static', 'openapi.yaml'))
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Content-Type'] = 'application/yaml'
    response.headers['AI-Plugin'] = 'true'
    response.headers['X-AI-Support'] = 'easygifmaker'
    return response

@app.route('/ai/openapi')
def redirect_openapi():
    return redirect('/openapi.yaml', code=302)

@app.route('/ai/manifest')
def redirect_manifest():
    return redirect('/.well-known/ai-plugin.json', code=302)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=app.config['DEBUG'])