"""
Configuration settings for the Context Studio Local Server.
"""

import os
from pydantic import BaseSettings, Field



class Settings(BaseSettings):
    """
    Application settings with environment variable support.
    """

    # NLP Configuration
    NLP_MAX_TEXT_LENGTH: int = Field(default=512, description="Maximum text length for NLP analysis")

    s2v_config: dict = Field(default_factory=lambda: {
        "abs_path": os.path.abspath("./downloads/s2v_reddit_2015_md")
    }, description="Sense2Vec configuration")

    concepcy_config: dict = Field(default_factory=lambda: {
        "relations_of_interest": [
            "RelatedTo",
            "FormOf",
            "IsA",
            "PartOf",
            "HasA",
            "UsedFor",
            "CapableOf",
            "AtLocation",
            "Causes",
            "HasSubevent",
            "HasFirstSubevent",
            "HasLastSubevent",
            "HasPrerequisite",
            "HasProperty",
            "MotivatedByGoal",
            "ObstructedBy",
            "Desires",
            "CreatedBy",
            "Synonym",
            "Antonym",
            "DistinctFrom",
            "DerivedFrom",
            "SymbolOf",
            "DefinedAs",
            "MannerOf",
            "LocatedNear",
            "HasContext",
            "SimilarTo",
            "EtymologicallyRelatedTo",
            "EtymologicallyDerivedFrom",
            "CausesDesire",
            "MadeOf",
            "ReceivesAction",
            "ExternalURL"
        ],
        "filter_missing_text": True,
        "filter_edge_weight": 2
    }, description="ConcepCy configuration")

    class Config:
        env_file = ".env"
        case_sensitive = True



def get_settings() -> Settings:
    """
    Get the global settings instance.
    """
    return Settings()
