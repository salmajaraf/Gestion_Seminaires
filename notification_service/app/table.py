from notification_service.app.database import Base, engine

Base.metadata.create_all(bind=engine)
