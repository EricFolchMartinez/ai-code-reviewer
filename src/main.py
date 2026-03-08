import argparse
import sys
from typing import Dict

from src.utils.config import Config
from src.utils.logger import setup_logger
from src.analyzer.file_reader import LocalFileReader
from src.ai_engine.llm_client import GroqClient
from src.reports.generator import ReportGenerator

logger = setup_logger(__name__)

def main() -> None:
    """
    Entry point of the AI Code Reviewer application.
    """
    logger.info("Starting AI Code Reviewer...")

    # If the API key is missing, the thread dies
    try:
        Config.validate()
    except ValueError as e:
        logger.error(e)
        sys.exit(1)

    # Parse the arguments
    parser = argparse.ArgumentParser(description="AI Automated Code Reviewer & Analyzer")
    parser.add_argument(
        "directory", 
        type=str, 
        help="Path to the directory containing the source code to analyze."
    )
    args = parser.parse_args()
    
    target_dir = args.directory

    # Read local files
    logger.info(f"Scanning directory: {target_dir}")
    try:
        files_data = LocalFileReader.read_directory(target_dir)
    except FileNotFoundError as e:
        logger.error(e)
        sys.exit(1)

    if not files_data:
        logger.warning("No supported files found in the specified directory.")
        sys.exit(0)
        
    logger.info(f"Found {len(files_data)} supported file(s) for analysis.")

    # Initialize AI client and analyze the files
    ai_client = GroqClient()
    reviews: Dict[str, str] = {}

    # In the future awayt/async instructions can be implemented (the program uses a free trial API key plan)
    for file_path, content in files_data.items():
        logger.info(f"Analyzing {file_path}...")
        review = ai_client.analyze_code(file_path, content)
        reviews[file_path] = review

    # Generate report
    logger.info("Generating final markdown report...")
    report_path = ReportGenerator.generate_markdown_report(reviews)
    
    if report_path:
        logger.info(f"Process completed successfully! Review your report at: {report_path}")
    else:
        logger.error("Process finished, but report generation failed.")

if __name__ == "__main__":
    main()