"""
Data models for the pipeline using Pydantic for validation.
"""
from typing import List
from pydantic import BaseModel, Field, validator
from datetime import datetime


class Group(BaseModel):
    """Represents a Monday.com group."""
    key: str = Field(..., description="Internal identifier for the group (e.g., 'overall', 'owned')")
    name: str = Field(..., description="Display name for the group (e.g., 'Overall Timeline')")
    
    @validator('key')
    def validate_key(cls, v):
        """Ensure key is lowercase and alphanumeric with underscores."""
        if not v.replace('_', '').isalnum():
            raise ValueError(f"Group key must be alphanumeric: {v}")
        return v.lower()


class Item(BaseModel):
    """Represents a Monday.com item with timeline data."""
    group_key: str = Field(..., description="Key of the group this item belongs to")
    name: str = Field(..., description="Name of the item/task")
    start_date: str = Field(..., description="Start date in YYYY-MM-DD format")
    end_date: str = Field(..., description="End date in YYYY-MM-DD format")
    
    @validator('start_date', 'end_date')
    def validate_date_format(cls, v):
        """Ensure dates are in YYYY-MM-DD format."""
        try:
            datetime.strptime(v, '%Y-%m-%d')
        except ValueError:
            raise ValueError(f"Date must be in YYYY-MM-DD format: {v}")
        return v
    
    @validator('end_date')
    def validate_end_after_start(cls, v, values):
        """Ensure end_date is not before start_date."""
        if 'start_date' in values:
            start = datetime.strptime(values['start_date'], '%Y-%m-%d')
            end = datetime.strptime(v, '%Y-%m-%d')
            if end < start:
                raise ValueError(f"End date {v} is before start date {values['start_date']}")
        return v


class BoardData(BaseModel):
    """Complete board structure with groups and items."""
    groups: List[Group] = Field(..., description="List of groups to create on the board")
    items: List[Item] = Field(..., description="List of items to create on the board")
    
    @validator('items')
    def validate_item_groups(cls, items, values):
        """Ensure all items reference valid groups."""
        if 'groups' in values:
            valid_keys = {g.key for g in values['groups']}
            for item in items:
                if item.group_key not in valid_keys:
                    raise ValueError(
                        f"Item '{item.name}' references unknown group key '{item.group_key}'"
                    )
        return items
    
    def to_dict(self) -> dict:
        """Convert to dictionary format."""
        return {
            "groups": [g.dict() for g in self.groups],
            "items": [i.dict() for i in self.items]
        }


# Writer API structured output schema
WRITER_SCHEMA = {
    "type": "object",
    "properties": {
        "groups": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "key": {
                        "type": "string",
                        "description": "Internal identifier (lowercase, alphanumeric with underscores)"
                    },
                    "name": {
                        "type": "string",
                        "description": "Display name for the group"
                    }
                },
                "required": ["key", "name"]
            },
            "description": "List of groups representing different project phases or categories"
        },
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "group_key": {
                        "type": "string",
                        "description": "Key of the group this item belongs to"
                    },
                    "name": {
                        "type": "string",
                        "description": "Name of the task or milestone"
                    },
                    "start_date": {
                        "type": "string",
                        "description": "Start date in YYYY-MM-DD format"
                    },
                    "end_date": {
                        "type": "string",
                        "description": "End date in YYYY-MM-DD format"
                    }
                },
                "required": ["group_key", "name", "start_date", "end_date"]
            },
            "description": "List of tasks/items with their timeline information"
        }
    },
    "required": ["groups", "items"]
}