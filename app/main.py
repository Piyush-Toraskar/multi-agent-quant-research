from contextlib import asynccontextmanager
from urllib.parse import urlsplit
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from app.config import ROOT, Settings
from app.database.queries import Repository
from app.service import ResearchService
from app.api.routes import router


def create_app(settings=None):
    settings = settings or Settings()
    @asynccontextmanager
    async def lifespan(app):
        repository = Repository(settings)
        repository.recover_interrupted()
        app.state.settings = settings
        app.state.repository = repository
        app.state.service = ResearchService(settings, repository)
        yield
        # Waiting is intentional: on a graceful shutdown, in-flight research is saved.
        app.state.service.close()
        repository.close()
    app = FastAPI(title='Multi-Agent Quant Research Platform', version='1.0.0', lifespan=lifespan, docs_url=None, redoc_url=None)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=['127.0.0.1', 'localhost', '[::1]', 'testserver'])
    @app.middleware('http')
    async def local_security(request: Request, call_next):
        origin = request.headers.get('origin')
        if origin:
            parsed = urlsplit(origin)
            if parsed.netloc != request.headers.get('host') or parsed.scheme not in {'http', 'https'}:
                return JSONResponse({'detail': 'Cross-origin requests are not allowed'}, status_code=403)
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'self'"
        return response
    @app.get('/docs', include_in_schema=False)
    def api_docs():
        return FileResponse(ROOT / 'app' / 'web' / 'docs.html')
    app.include_router(router)
    app.mount('/static', StaticFiles(directory=ROOT / 'app' / 'web'), name='static')
    @app.get('/', include_in_schema=False)
    def index():
        return FileResponse(ROOT / 'app' / 'web' / 'index.html')
    return app

app = create_app()
