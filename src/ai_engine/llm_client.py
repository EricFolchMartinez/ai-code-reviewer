from typing import Optional

from groq import Groq

from src.utils.config import Config
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

class GroqClient:
    """
    Client wrapper for the Groq API.
    Handles authentication and communication with the Llama 3 model.
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initializes the Groq client.

        Args:
            api_key (Optional[str]): An explicit Groq API key. When omitted, the
                Groq SDK falls back to the GROQ_API_KEY environment variable
                (loaded by the Config module). This lets the web layer pass a
                key provided at request time without mutating global state.

        We select 'llama-3.3-70b-versatile' because the 70 Billion parameter
        model is perfect for code analysis.
        """
        # Initialize the Groq client. Passing api_key=None lets the SDK read
        # the GROQ_API_KEY environment variable, preserving previous behaviour.
        self.client = Groq(api_key=api_key) if api_key else Groq()
        
        # The model used
        self.model = "llama-3.3-70b-versatile"
        logger.info(f"GroqClient initialized successfully with model: {self.model}")

    def analyze_code(self, file_name: str, code_content: str) -> str:
        """
        Sends the source code to the Groq LLM to analyze for Clean Code, SOLID principles,
        and potential bugs or inefficiencies.
        
        Args:
            file_name (str): The name/path of the file being analyzed.
            code_content (str): The raw source code of the file.
            
        Returns:
            str: The LLM's review in Markdown format.
        """
        system_prompt = (
            "You are a Senior Software Engineer acting as a strict but helpful Code Reviewer. "
            "Your task is to review the provided source code.\n"
            "Focus strictly on:\n"
            "1. SOLID Principles violations.\n"
            "2. Clean Code practices (naming conventions, function length, DRY, KISS).\n"
            "3. Security vulnerabilities and performance bottlenecks.\n\n"
            "Provide your response in clear Markdown. Structure the review with:\n"
            "- Overall Assessment\n"
            "- Key Issues\n"
            "- Suggested Code Improvements (provide short code snippets if necessary).\n"
            "If the code is already excellent, praise the author."
        )

        user_prompt = f"Please review the following file '{file_name}':\n\n```\n{code_content}\n```"

        try:
            logger.info(f"Sending file '{file_name}' to Groq for analysis...")
            
            # Create a chat interface
            chat_completion = self.client.chat.completions.create(
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt
                    },
                    {
                        "role": "user",
                        "content": user_prompt
                    }
                ],
                model=self.model,
                temperature=0.2, # Low temperature fot analytical tasks
                max_tokens=2048   # Ensure we have enough tokens for the task
            )
            
            # Extract the text from the AI response
            review = chat_completion.choices[0].message.content
            return review if review else "Error: Empty response from LLM."
            
        except Exception as e:
            logger.error(f"Failed to analyze code with Groq API. Error: {e}")
            return f"Error: Could not analyze {file_name}. Check logs for details."