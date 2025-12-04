"""
Monday.com API client for creating boards, groups, and items.
"""
import requests
import json
import logging
from typing import Dict, List, Tuple

from config import Config
from models import BoardData, Group, Item

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MondayClient:
    """Client for interacting with Monday.com GraphQL API."""
    
    def __init__(self):
        """Initialize the Monday.com client."""
        self.api_url = Config.MONDAY_API_URL
        self.headers = Config.get_monday_headers()
    
    def _run_query(self, query: str, variables: dict = None) -> dict:
        """
        Execute a GraphQL query/mutation against Monday.com API.
        
        Args:
            query: GraphQL query string
            variables: Optional variables for the query
            
        Returns:
            Response data dictionary
            
        Raises:
            Exception: If the API returns errors
        """
        payload = {
            "query": query,
            "variables": variables or {}
        }
        
        response = requests.post(self.api_url, json=payload, headers=self.headers)
        data = response.json()
        
        if "errors" in data:
            error_msg = json.dumps(data["errors"], indent=2)
            raise Exception(f"Monday.com API error:\n{error_msg}")
        
        return data["data"]
    
    def create_board(self, name: str) -> str:
        """
        Create a new public board.
        
        Args:
            name: Name of the board
            
        Returns:
            Board ID
        """
        logger.info(f"Creating public board: {name}")
        
        mutation = """
        mutation($name: String!) {
            create_board(board_name: $name, board_kind: public) {
                id
            }
        }
        """
        
        result = self._run_query(mutation, {"name": name})
        board_id = result["create_board"]["id"]
        
        logger.info(f"Created board with ID: {board_id}")
        return board_id
    
    def create_groups(self, board_id: str, groups: List[Group]) -> Dict[str, str]:
        """
        Create groups on a board.
        
        Args:
            board_id: ID of the board
            groups: List of Group objects
            
        Returns:
            Dictionary mapping group keys to group IDs
        """
        logger.info(f"Creating {len(groups)} groups on board {board_id}")
        
        group_ids = {}
        
        for group in groups:
            mutation = """
            mutation($board_id: ID!, $name: String!) {
                create_group(board_id: $board_id, group_name: $name) {
                    id
                }
            }
            """
            
            result = self._run_query(
                mutation,
                {"board_id": board_id, "name": group.name}
            )
            
            group_id = result["create_group"]["id"]
            group_ids[group.key] = group_id
            logger.info(f"  Created group '{group.name}' (key: {group.key}) → {group_id}")
        
        return group_ids
    
    def create_timeline_column(self, board_id: str) -> None:
        """
        Create a timeline column on a board.
        
        Args:
            board_id: ID of the board
        """
        logger.info(f"Creating timeline column on board {board_id}")
        
        mutation = """
        mutation($board_id: ID!) {
            create_column(
                board_id: $board_id,
                title: "Timeline",
                id: "timeline",
                column_type: timeline
            ) {
                id
            }
        }
        """
        
        self._run_query(mutation, {"board_id": board_id})
        logger.info("Timeline column created successfully")
    
    def create_items_batch(
        self,
        board_id: str,
        items: List[Item],
        group_ids: Dict[str, str]
    ) -> None:
        """
        Create multiple items in a single batched mutation.
        
        Args:
            board_id: ID of the board
            items: List of Item objects
            group_ids: Dictionary mapping group keys to group IDs
        """
        logger.info(f"Creating {len(items)} items in batch")
        
        # Build batched mutation
        mutation_parts = ["mutation {"]
        
        for idx, item in enumerate(items):
            alias = f"item_{idx}"
            
            # Get the group ID for this item
            if item.group_key not in group_ids:
                logger.warning(f"Unknown group key '{item.group_key}' for item '{item.name}', skipping")
                continue
            
            group_id = group_ids[item.group_key]
            
            # Build column values JSON
            column_values = {
                "timeline": {
                    "from": item.start_date,
                    "to": item.end_date
                }
            }
            column_values_json = json.dumps(column_values)
            
            # Escape for GraphQL string
            column_values_escaped = column_values_json.replace('\\', '\\\\').replace('"', '\\"')
            item_name_escaped = item.name.replace('"', '\\"')
            
            # Add mutation for this item
            mutation_parts.append(f"""
                {alias}: create_item(
                    board_id: {board_id},
                    group_id: "{group_id}",
                    item_name: "{item_name_escaped}",
                    column_values: "{column_values_escaped}"
                ) {{
                    id
                }}
            """)
        
        mutation_parts.append("}")
        mutation = "\n".join(mutation_parts)
        
        # Execute the batched mutation
        self._run_query(mutation)
        logger.info(f"Successfully created {len(items)} items")
    
    def create_board_from_data(
        self,
        board_name: str,
        board_data: BoardData
    ) -> Tuple[str, Dict[str, str]]:
        """
        Create a complete board with groups, timeline column, and items.
        
        Args:
            board_name: Name for the new board
            board_data: BoardData object with groups and items
            
        Returns:
            Tuple of (board_id, group_ids_dict)
        """
        logger.info(f"Creating complete board: {board_name}")
        
        # Step 1: Create board
        board_id = self.create_board(board_name)
        
        # Step 2: Create groups
        group_ids = self.create_groups(board_id, board_data.groups)
        
        # Step 3: Create timeline column
        self.create_timeline_column(board_id)
        
        # Step 4: Create all items
        self.create_items_batch(board_id, board_data.items, group_ids)
        
        logger.info(f"✅ Board creation complete! Board ID: {board_id}")
        
        return board_id, group_ids