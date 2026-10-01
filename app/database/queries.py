import uuid
from sqlalchemy import select, update
from app.database.models import ResearchRun, AgentEvent, now
from app.database.db import make_engine
from app.storage import sanitise


def serialise_run(row, detail=False):
    result = {'id': row.id, 'query': row.query, 'status': row.status,
              'created_at': row.created_at.isoformat(), 'updated_at': row.updated_at.isoformat(),
              'error': row.error}
    if detail:
        result.update(request=row.request, result=row.result)
    return result

class Repository:
    def __init__(self, settings):
        self.engine, self.session = make_engine(settings)

    def close(self):
        self.engine.dispose()

    def create(self, request):
        identifier = uuid.uuid4().hex
        with self.session.begin() as db:
            db.add(ResearchRun(id=identifier, query=request['query'], request=request, status='queued'))
        return identifier

    def update(self, identifier, **fields):
        fields['updated_at'] = now()
        with self.session.begin() as db:
            db.execute(update(ResearchRun).where(ResearchRun.id == identifier).values(**sanitise(fields)))

    def get(self, identifier):
        with self.session() as db:
            row = db.get(ResearchRun, identifier)
            return serialise_run(row, True) if row else None

    def search(self, query='', limit=20):
        limit = max(1, min(int(limit), 100))
        statement = select(ResearchRun)
        if query:
            statement = statement.where(ResearchRun.query.contains(query, autoescape=True))
        with self.session() as db:
            rows = db.scalars(statement.order_by(ResearchRun.created_at.desc()).limit(limit))
            return [serialise_run(row) for row in rows]

    def event(self, run_id, agent, kind, detail):
        with self.session.begin() as db:
            db.add(AgentEvent(run_id=run_id, agent=agent, kind=kind, detail=sanitise(detail)))

    def events(self, run_id, after=0):
        with self.session() as db:
            rows = db.scalars(select(AgentEvent).where(AgentEvent.run_id == run_id, AgentEvent.id > after)
                              .order_by(AgentEvent.id).limit(500))
            return [{'id': r.id, 'timestamp': r.timestamp.isoformat(), 'agent': r.agent,
                     'kind': r.kind, 'detail': r.detail} for r in rows]

    def recover_interrupted(self):
        with self.session.begin() as db:
            db.execute(update(ResearchRun).where(ResearchRun.status.in_(['queued', 'running']))
                       .values(status='interrupted', error='Application stopped before this run completed. Resubmit the request.', updated_at=now()))
