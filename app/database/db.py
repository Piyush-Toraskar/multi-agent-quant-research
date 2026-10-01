from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from app.database.models import Base


def make_engine(settings):
    settings.prepare()
    kwargs = {'pool_pre_ping': True}
    if settings.database_url.startswith('sqlite'):
        kwargs['connect_args'] = {'check_same_thread': False, 'timeout': 30}
    engine = create_engine(settings.database_url, **kwargs)
    if settings.database_url.startswith('sqlite'):
        @event.listens_for(engine, 'connect')
        def sqlite_pragmas(connection, _):
            cursor = connection.cursor()
            cursor.execute('PRAGMA journal_mode=WAL')
            cursor.execute('PRAGMA busy_timeout=30000')
            cursor.execute('PRAGMA foreign_keys=ON')
            cursor.close()
    Base.metadata.create_all(engine)
    return engine, sessionmaker(bind=engine, expire_on_commit=False)
