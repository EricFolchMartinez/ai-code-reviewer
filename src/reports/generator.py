from datetime import datetime
from pathlib import Path
from typing import Dict

from src.utils.logger import setup_logger

logger = setup_logger(__name__)

class ReportGenerator:
    """
    Handles the creation of output reports.
    """

    @staticmethod
    def generate_markdown_report(reviews: Dict[str, str], output_dir: str = "output") -> str:
        """
        Takes a dictionary of file reviews and compiles them into a single Markdown file.
        
        Args:
            reviews (Dict[str, str]): Dictionary where keys are file paths and values are the LLM reviews.
            output_dir (str): The folder where the report will be saved. Defaults to 'output'.
            
        Returns:
            str: The absolute path to the generated report file.
        """
        if not reviews:
            logger.warning("No reviews provided to generate a report.")
            return ""

        # Create output directory in the root directory
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)

        # Generate a filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_filename = f"code_review_report_{timestamp}.md"
        report_file_path = out_path / report_filename

        try:
            with open(report_file_path, "w", encoding="utf-8") as file:
                # Write the header of the report
                file.write("# AI Code Review Report\n\n")
                file.write(f"**Generated on:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                file.write("---\n\n")

                # Iterate through each reviewed file and append it to the report
                for file_path, review_content in reviews.items():
                    file.write(f"## File: `{file_path}`\n\n")
                    file.write(f"{review_content}\n\n")
                    file.write("---\n\n")

            logger.info(f"Report successfully generated at: {report_file_path.absolute()}")
            return str(report_file_path.absolute())

        except IOError as e:
            logger.error(f"Failed to write the report file. Error: {e}")
            return ""