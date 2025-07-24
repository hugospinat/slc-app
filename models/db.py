from sqlmodel import SQLModel, create_engine

DATABASE_URL = "sqlite:///database.db"
engine = create_engine(DATABASE_URL)


def clear_registry() -> None:
    """Nettoyer le registre SQLModel pour éviter les conflits"""
    SQLModel.metadata.clear()


def create_db_and_tables() -> None:
    """Créer les tables de base de données"""
    SQLModel.metadata.create_all(engine)
