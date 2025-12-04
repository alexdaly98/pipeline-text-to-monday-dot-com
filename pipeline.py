"""
Main pipeline orchestration for extracting timeline data and creating Monday.com boards.
"""
import argparse
import logging
import sys
from pathlib import Path
from typing import Optional

from config import Config
from writer_client import WriterClient
from monday_client import MondayClient
from models import BoardData

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TimelinePipeline:
    """Orchestrates the end-to-end timeline extraction and board creation."""
    
    def __init__(self):
        """Initialize the pipeline with API clients."""
        Config.validate()
        self.writer_client = WriterClient()
        self.monday_client = MondayClient()
    
    def run_from_csv(
        self,
        csv_path: str,
        board_name: str
    ) -> tuple[str, dict[str, str]]:
        """
        Run the complete pipeline from a CSV file.
        
        Args:
            csv_path: Path to the CSV file
            board_name: Name for the Monday.com board
            
        Returns:
            Tuple of (board_id, group_ids_dict)
        """
        logger.info("=" * 60)
        logger.info("STARTING PIPELINE: CSV → Monday.com Board")
        logger.info("=" * 60)
        
        # Step 1: Extract data from CSV
        logger.info("\n[1/2] Extracting timeline data from CSV...")
        board_data = self.writer_client.extract_from_csv(csv_path)
        
        # Step 2: Create Monday.com board
        logger.info("\n[2/2] Creating Monday.com board...")
        board_id, group_ids = self.monday_client.create_board_from_data(
            board_name,
            board_data
        )
        
        logger.info("\n" + "=" * 60)
        logger.info("🎉 PIPELINE COMPLETE!")
        logger.info(f"Board ID: {board_id}")
        logger.info(f"Groups created: {len(group_ids)}")
        logger.info(f"Items created: {len(board_data.items)}")
        logger.info("=" * 60)
        
        return board_id, group_ids
    
    def run_from_text(
        self,
        text: str,
        board_name: str
    ) -> tuple[str, dict[str, str]]:
        """
        Run the complete pipeline from free-form text.
        
        Args:
            text: Free-form text describing timeline
            board_name: Name for the Monday.com board
            
        Returns:
            Tuple of (board_id, group_ids_dict)
        """
        logger.info("=" * 60)
        logger.info("STARTING PIPELINE: Text → Monday.com Board")
        logger.info("=" * 60)
        
        # Step 1: Extract data from text
        logger.info("\n[1/2] Extracting timeline data from text...")
        board_data = self.writer_client.extract_from_text(text)
        
        # Step 2: Create Monday.com board
        logger.info("\n[2/2] Creating Monday.com board...")
        board_id, group_ids = self.monday_client.create_board_from_data(
            board_name,
            board_data
        )
        
        logger.info("\n" + "=" * 60)
        logger.info("🎉 PIPELINE COMPLETE!")
        logger.info(f"Board ID: {board_id}")
        logger.info(f"Groups created: {len(group_ids)}")
        logger.info(f"Items created: {len(board_data.items)}")
        logger.info("=" * 60)
        
        return board_id, group_ids
    
    def run_from_text_file(
        self,
        text_path: str,
        board_name: str
    ) -> tuple[str, dict[str, str]]:
        """
        Run the complete pipeline from a text file.
        
        Args:
            text_path: Path to the text file
            board_name: Name for the Monday.com board
            
        Returns:
            Tuple of (board_id, group_ids_dict)
        """
        text_path = Path(text_path)
        if not text_path.exists():
            raise FileNotFoundError(f"Text file not found: {text_path}")
        
        with open(text_path, 'r', encoding='utf-8') as f:
            text = f.read()
        
        return self.run_from_text(text, board_name)


def main():
    """Command-line interface for the pipeline."""
    parser = argparse.ArgumentParser(
        description="Extract timeline data and create Monday.com boards"
    )
    
    parser.add_argument(
        '--csv',
        type=str,
        help='Path to CSV file containing timeline data'
    )
    
    parser.add_argument(
        '--text',
        type=str,
        help='Path to text file containing timeline description'
    )
    
    parser.add_argument(
        '--text-input',
        type=str,
        help='Direct text input (alternative to --text file)'
    )
    
    parser.add_argument(
        '--board-name',
        type=str,
        required=True,
        help='Name for the Monday.com board'
    )
    
    args = parser.parse_args()
    
    # Validate input arguments
    input_count = sum([
        args.csv is not None,
        args.text is not None,
        args.text_input is not None
    ])
    
    if input_count == 0:
        parser.error("Must provide one of: --csv, --text, or --text-input")
    
    if input_count > 1:
        parser.error("Provide only one input method: --csv, --text, or --text-input")
    
    try:
        pipeline = TimelinePipeline()
        
        if args.csv:
            board_id, _ = pipeline.run_from_csv(args.csv, args.board_name)
        elif args.text:
            board_id, _ = pipeline.run_from_text_file(args.text, args.board_name)
        else:  # args.text_input
            board_id, _ = pipeline.run_from_text(args.text_input, args.board_name)
        
        print(f"\n✅ Success! Board created: {board_id}")
        sys.exit(0)
        
    except Exception as e:
        logger.error(f"Pipeline failed: {str(e)}", exc_info=True)
        print(f"\n❌ Error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()