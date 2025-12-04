"""
Writer API client for extracting structured data from CSV or free-form text.
"""
import requests
import json
import logging
from typing import List, Union
from pathlib import Path

from config import Config
from models import BoardData, WRITER_SCHEMA

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class WriterClient:
    """Client for interacting with Writer's structured output API."""
    
    def __init__(self):
        """Initialize the Writer client."""
        self.headers = Config.get_writer_headers()
        self.model = Config.WRITER_MODEL
        self.max_units = Config.WRITER_MAX_UNITS
    
    def _build_extraction_prompt(self, text: str, is_partial: bool = False) -> str:
        """
        Build the prompt for Writer to extract structured data.
        
        Args:
            text: Input text (CSV or free-form)
            is_partial: Whether this is a partial chunk of a larger input
            
        Returns:
            Formatted prompt string
        """
        base_prompt = """Extract project timeline information from the following text.

Identify:
1. Groups: Different phases or categories of work (e.g., "Overall Timeline", "Email Development")
   - Assign a short lowercase key for each group (e.g., "overall", "email")
   - Provide a descriptive display name

2. Items: Individual tasks or milestones with:
   - The group they belong to (using the group key)
   - Task name
   - Start date in YYYY-MM-DD format
   - End date in YYYY-MM-DD format

If dates are in other formats (e.g., "Oct 29", "10/29/2025"), convert them to YYYY-MM-DD.
If the year is not specified somewhere assume it's 2025.
If a task has only one date mentioned, use the same date for both start and end.
"""
        
        if is_partial:
            base_prompt += "\nNote: This is a partial chunk of a larger dataset. Extract all information present.\n"
        
        base_prompt += f"\n\nInput:\n{text}\n\nExtract the groups and items as structured JSON."
        
        return base_prompt
    
    def _estimate_units(self, text: str) -> int:
        """
        Estimate the number of Writer API units for a given text.
        Rough approximation: 1 unit ≈ 4 characters.
        
        Args:
            text: Input text
            
        Returns:
            Estimated units
        """
        return len(text) // 4
    
    def _chunk_text(self, text: str) -> List[str]:
        """
        Split text into chunks that fit within Writer's unit limits.
        
        Args:
            text: Input text to chunk
            
        Returns:
            List of text chunks
        """
        lines = text.strip().split('\n')
        chunks = []
        current_chunk = []
        current_size = 0
        
        # Reserve space for prompt overhead
        max_chunk_size = self.max_units * 3  # ~75 units worth of input text
        
        for line in lines:
            line_size = len(line)
            
            if current_size + line_size > max_chunk_size and current_chunk:
                # Save current chunk
                chunks.append('\n'.join(current_chunk))
                current_chunk = []
                current_size = 0
            
            current_chunk.append(line)
            current_size += line_size
        
        # Add remaining lines
        if current_chunk:
            chunks.append('\n'.join(current_chunk))
        
        logger.info(f"Split input into {len(chunks)} chunks")
        return chunks
    
    def _call_writer_api(self, prompt: str) -> dict:
        """
        Make a single API call to Writer with structured output.
        
        Args:
            prompt: The extraction prompt
            
        Returns:
            Parsed JSON response
            
        Raises:
            Exception: If API call fails
        """
        # Writer uses /v1/chat endpoint
        api_url = "https://api.writer.com/v1/chat"
        print(prompt)
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "timeline_extraction",
                    "schema": WRITER_SCHEMA
                }
            },
            "temperature": 0  # Low temperature for consistent extraction
        }
        
        logger.info("Calling Writer API...")
        response = requests.post(api_url, headers=self.headers, json=payload)
        
        if response.status_code != 200:
            raise Exception(f"Writer API error: {response.status_code} - {response.text}")
        
        result = response.json()
        
        if "choices" not in result or not result["choices"]:
            raise Exception(f"Unexpected Writer API response: {result}")
        
        content = result["choices"][0]["message"]["content"]
        return json.loads(content)
    
    def _merge_results(self, results: List[dict]) -> dict:
        """
        Merge multiple extraction results into a single structure.
        Deduplicates groups by key and combines all items.
        
        Args:
            results: List of extraction results from multiple chunks
            
        Returns:
            Merged result dictionary
        """
        merged_groups = {}
        all_items = []
        
        for result in results:
            # Merge groups (deduplicate by key)
            for group in result.get("groups", []):
                key = group["key"]
                if key not in merged_groups:
                    merged_groups[key] = group
            
            # Collect all items
            all_items.extend(result.get("items", []))
        
        return {
            "groups": list(merged_groups.values()),
            "items": all_items
        }
    
    def extract_from_text(self, text: str) -> BoardData:
        """
        Extract board data from free-form text.
        
        Args:
            text: Free-form text describing timeline
            
        Returns:
            Validated BoardData object
        """
        logger.info("Extracting from text input")
        
        # Check if chunking is needed
        estimated_units = self._estimate_units(text)
        
        if estimated_units <= self.max_units:
            # Single request
            prompt = self._build_extraction_prompt(text)
            result = self._call_writer_api(prompt)
        else:
            # Multiple requests with chunking
            logger.info(f"Input too large ({estimated_units} units), chunking...")
            chunks = self._chunk_text(text)
            results = []
            
            for i, chunk in enumerate(chunks, 1):
                logger.info(f"Processing chunk {i}/{len(chunks)}")
                prompt = self._build_extraction_prompt(chunk, is_partial=True)
                result = self._call_writer_api(prompt)
                results.append(result)
            
            result = self._merge_results(results)
        
        # Validate and return
        board_data = BoardData(**result)
        ### Log perso
        print(result)
        logger.info(f"Extracted {len(board_data.groups)} groups and {len(board_data.items)} items")
        return board_data
    
    def extract_from_csv(self, csv_path: Union[str, Path]) -> BoardData:
        """
        Extract board data from a CSV file.
        
        Expected CSV format:
        - Header row with: group_key, group_name, item_name, start_date, end_date
        - Or simpler format that will be interpreted by LLM
        
        Args:
            csv_path: Path to CSV file
            
        Returns:
            Validated BoardData object
        """
        logger.info(f"Extracting from CSV: {csv_path}")
        
        csv_path = Path(csv_path)
        if not csv_path.exists():
            raise FileNotFoundError(f"CSV file not found: {csv_path}")
        
        # Read CSV as text and let Writer parse it
        with open(csv_path, 'r', encoding='utf-8') as f:
            csv_content = f.read()
        
        return self.extract_from_text(csv_content)