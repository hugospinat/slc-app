"""
Utilitaire générique pour créer des objets SQLModel depuis des DataFrames
"""

from typing import TypeVar, Type, List
import pandas as pd
from sqlmodel import SQLModel

T = TypeVar("T", bound=SQLModel)


def create_objects_from_df(model_class: Type[T], df: pd.DataFrame) -> List[T]:
    """
    Factory générique pour créer des objets SQLModel depuis un DataFrame.

    Les noms de colonnes du DataFrame doivent correspondre exactement
    aux noms des champs du modèle.

    Args:
        model_class: La classe du modèle (Facture, Poste, etc.)
        df: Le DataFrame source avec les bonnes colonnes

    Returns:
        Liste d'objets du modèle créés
    """
    return [model_class(**row.to_dict()) for _, row in df.iterrows()]
