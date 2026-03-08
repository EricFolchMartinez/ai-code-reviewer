from pathlib import Path
from typing import Dict, Set
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class LocalFileReader:
    """
    Responsible for reading source code files from the local file system.
    """
    
    # Defined suported exensions to avoid reading binary files.
    SUPPORTED_EXTENSIONS: Set[str] = {'.py', '.js', '.ts', '.html', '.css', '.java', '.cpp', '.c'}

    @classmethod
    def read_directory(cls, directory_path: str) -> Dict[str, str]:
        """
        Goes through a directory and reads the content of all supported source code files.
        
        Args:
            directory_path (str): The path to the directory to analyze.
            
        Returns:
            Dict[str, str]: A dictionary where the key is the file path and the value is the file content.
            
        Raises:
            FileNotFoundError: If the provided directory does not exist.
        """
        path = Path(directory_path)
        
        if not path.exists() or not path.is_dir():
            raise FileNotFoundError(f"The directory '{directory_path}' does not exist or is not a valid directory.")

        files_content: Dict[str, str] = {}
        
        
        for file_path in path.rglob('*'): # recursive function that searches all files inside the directory
            if file_path.is_file() and file_path.suffix in cls.SUPPORTED_EXTENSIONS:
                try:
                    with open(file_path, 'r', encoding='utf-8') as file:
                        files_content[str(file_path)] = file.read()
                except Exception as e:
                    logger.warning(f"Could not read file {file_path}. Error: {e}")   
                                     
        return files_content