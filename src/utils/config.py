import os
from dotenv import load_dotenv

# Load environment variables from a local .env file
load_dotenv()

class Config:
    """
    Centralized configuration class.
    Prevents hardcoding sensitive data and magic strings across the application.
    """
    
    # Environment variables
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
    
    @classmethod
    def validate(cls) -> None:
        """
        Validates that all required environment variables are set.
        Implements the 'Fail Fast': aborts execution if config is missing.
        """
        
        if not cls.LLM_API_KEY:
            raise ValueError(
                "CRITICAL ERROR: LLM_API_KEY environment variable is not set. "
                "Please check your .env file."
            )