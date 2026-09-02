from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, DateTime, JSON, func
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
import datetime

Base = declarative_base()

class Worker(Base):
    __tablename__ = 'workers'
    id = Column(Integer, primary_key=True)
    nickname = Column(String, unique=True, nullable=False)

class Project(Base):
    __tablename__ = 'projects'
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    description = Column(String)

class Annotation(Base):
    __tablename__ = 'annotations'
    id = Column(Integer, primary_key=True)
    nickname = Column(String, ForeignKey('workers.nickname'), nullable=False)
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=False)
    task_id = Column(String, nullable=False)
    info = Column(JSON)
    datetime = Column(DateTime, default=datetime.datetime.utcnow)
    
    worker = relationship('Worker')
    project = relationship('Project')

class AnnotationDatabase:
    def __init__(self, db_url='sqlite:///annotations.db'):
        self.engine = create_engine(db_url)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

        self.session = None
    
    def __enter__(self):
        self.session = self.Session()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            if exc_type is None:
                self.session.commit()
            else:
                self.session.rollback()
        finally:
            self.session.close()
            self.session = None
    
    def add_project_if_not_exists(self, name, description=None):
        project = self.session.query(Project).filter_by(name=name).first()
        if project is not None:
            return project
            
        project = Project(name=name, description=description)
        self.session.add(project)
        return project
    
    def add_worker_if_not_exists(self, nickname):
        worker = self.session.query(Worker).filter_by(nickname=nickname).first()
        if worker is not None:
            return worker
            
        worker = Worker(nickname=nickname)
        self.session.add(worker)
        return worker
    
    def add_annotation(self, nickname, project_name, task_id, info=None):
        worker = self.add_worker_if_not_exists(nickname)
        project = self.add_project_if_not_exists(project_name)
        
        annotation = self.session.query(Annotation).filter_by(nickname=nickname, project_id=project.id, task_id=task_id).first()
        if annotation is not None:
            annotation.info = info
            return

        annotation = Annotation(nickname=nickname, project_id=project.id, task_id=task_id, info=info)
        self.session.add(annotation)

    def get_annotations_by_project(self, project_name):
        project = self.session.query(Project).filter_by(name=project_name).first()
        if project is None:
            return
        
        annotations = self.session.query(Annotation).filter_by(project_id=project.id).all()
        return annotations

    def get_annotations_by_project_worker(self, project_name, nickname):
        project = self.session.query(Project).filter_by(name=project_name).first()
        if project is None:
            return []
        annotations = self.session.query(Annotation).filter_by(project_id=project.id, nickname=nickname).all()
        return annotations

    def get_annotation(self, nickname, project_name, task_id):
        project = self.session.query(Project).filter_by(name=project_name).first()
        worker = self.session.query(Worker).filter_by(nickname=nickname).first()
        if project is None or worker is None:
            return
            
        annotation = self.session.query(Annotation).filter_by(nickname=nickname, project_id=project.id, task_id=task_id).first()
        return annotation

    def get_annotation_info(self, nickname, project_name, task_id):
        annotation = self.get_annotation(nickname, project_name, task_id)
        if annotation is None:
            return
        return annotation.info


# Пример использования god-object
if __name__ == "__main__":
    DB = AnnotationDatabase()
#    with DB as db:
#        db.add_annotation("nickname1", "Proj", task_id='abc', info=None)
#        db.add_annotation("nickname2", "Proj", task_id='abc', info={"label": "1", 'label2': "1"})
        
    with DB as db:
            annotations = db.get_annotations_by_project("DSAT_init")
            for annotation in annotations:
                print(f"Annotation ID: {annotation.id}, Worker: {annotation.nickname}, Task ID: {annotation.task_id}, Info: {annotation.info}, DateTime: {annotation.datetime}")

#    with DB as db:
#        print(db.get_annotation_info('nickname2', 'Proj', 'abc'))
#        print(db.get_annotation_info('nickname1', 'Proj', 'abc'))
#        print(db.get_annotation_info('nickname1', 'Proj', 'cde'))
