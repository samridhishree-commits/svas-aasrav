"""Run once: python -m backend.init_db. No road import or APOC required."""
from .config import Settings
from .database import Database
from .errors import ServiceError

if __name__ == '__main__':
    db=Database(Settings())
    try:
        db.initialize()
        print('svas-aasrav graph constraints are ready.')
    except ServiceError as error:
        print(error.message)
        raise SystemExit(1)
    finally:
        db.close()
