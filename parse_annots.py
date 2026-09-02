import pandas as pd
from .database import AnnotationDatabase

PATH_TO_DB_FILE = '/path/to/db/file'

DB = AnnotationDatabase(db_url=f'sqlite:///{PATH_TO_DB_FILE}')

def to_dict(row):
    return {column.name: getattr(row, row.__mapper__.get_property_by_column(column).key) for column in row.__table__.columns}
    
def fetch_by_collection_id(collection_id):
    with DB as db:
        res = db.get_annotations_by_project(collection_id)
        data = [to_dict(r) for r in res]
    
    df = pd.DataFrame(data)
    return df
