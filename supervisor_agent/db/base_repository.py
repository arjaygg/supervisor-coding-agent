"""
Generic Repository Pattern for Database Operations
Eliminates DRY violations by providing reusable CRUD operations.
"""
from typing import TypeVar, Generic, Type, Optional, List, Any, Dict, Union
from sqlalchemy.orm import Session
from sqlalchemy.ext.declarative import DeclarativeMeta
from sqlalchemy import desc, and_
from datetime import datetime, timedelta
from pydantic import BaseModel

# Type variables for generic repository
ModelType = TypeVar('ModelType', bound=DeclarativeMeta)
CreateSchemaType = TypeVar('CreateSchemaType', bound=BaseModel)
UpdateSchemaType = TypeVar('UpdateSchemaType', bound=BaseModel)


class BaseRepository(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    """Generic repository providing common CRUD operations."""
    
    def __init__(self, model: Type[ModelType]):
        self.model = model
    
    def create(self, db: Session, obj_in: CreateSchemaType) -> ModelType:
        """Create a new object in the database."""
        obj_data = obj_in.model_dump() if hasattr(obj_in, 'model_dump') else obj_in.dict()
        db_obj = self.model(**obj_data)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj
    
    def get(self, db: Session, id: Any) -> Optional[ModelType]:
        """Get an object by its ID."""
        return db.query(self.model).filter(self.model.id == id).first()
    
    def get_multi(
        self, 
        db: Session, 
        *, 
        skip: int = 0, 
        limit: int = 100,
        order_by: Optional[str] = None
    ) -> List[ModelType]:
        """Get multiple objects with pagination."""
        query = db.query(self.model)
        
        if order_by:
            if hasattr(self.model, order_by):
                order_column = getattr(self.model, order_by)
                query = query.order_by(desc(order_column))
        
        return query.offset(skip).limit(limit).all()
    
    def update(
        self, 
        db: Session, 
        *, 
        db_obj: ModelType, 
        obj_in: Union[UpdateSchemaType, Dict[str, Any]]
    ) -> ModelType:
        """Update an existing object."""
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.dict(exclude_unset=True) if hasattr(obj_in, 'dict') else obj_in.model_dump(exclude_unset=True)
        
        for field, value in update_data.items():
            setattr(db_obj, field, value)
        
        db.commit()
        db.refresh(db_obj)
        return db_obj
    
    def update_by_id(
        self, 
        db: Session, 
        *, 
        id: Any, 
        obj_in: Union[UpdateSchemaType, Dict[str, Any]]
    ) -> Optional[ModelType]:
        """Update an object by its ID."""
        db_obj = self.get(db, id)
        if db_obj:
            return self.update(db, db_obj=db_obj, obj_in=obj_in)
        return None
    
    def delete(self, db: Session, *, id: Any) -> Optional[ModelType]:
        """Delete an object by its ID."""
        obj = self.get(db, id)
        if obj:
            db.delete(obj)
            db.commit()
        return obj
    
    def get_by_field(
        self, 
        db: Session, 
        field_name: str, 
        field_value: Any
    ) -> Optional[ModelType]:
        """Get an object by a specific field value."""
        if hasattr(self.model, field_name):
            field = getattr(self.model, field_name)
            return db.query(self.model).filter(field == field_value).first()
        return None
    
    def get_multi_by_field(
        self, 
        db: Session, 
        field_name: str, 
        field_value: Any,
        skip: int = 0,
        limit: int = 100
    ) -> List[ModelType]:
        """Get multiple objects by a specific field value."""
        if hasattr(self.model, field_name):
            field = getattr(self.model, field_name)
            return (
                db.query(self.model)
                .filter(field == field_value)
                .offset(skip)
                .limit(limit)
                .all()
            )
        return []
    
    def count(self, db: Session) -> int:
        """Count total objects."""
        return db.query(self.model).count()
    
    def exists(self, db: Session, id: Any) -> bool:
        """Check if an object exists by ID."""
        return db.query(self.model).filter(self.model.id == id).first() is not None


class TimestampMixin:
    """Mixin for repositories that need timestamp-based queries."""
    
    def get_recent(
        self, 
        db: Session, 
        hours: int = 24,
        timestamp_field: str = 'created_at'
    ) -> List[ModelType]:
        """Get objects created within the last N hours."""
        if hasattr(self.model, timestamp_field):
            cutoff = datetime.utcnow() - timedelta(hours=hours)
            timestamp_column = getattr(self.model, timestamp_field)
            return db.query(self.model).filter(timestamp_column >= cutoff).all()
        return []
    
    def get_between_dates(
        self,
        db: Session,
        start_date: datetime,
        end_date: datetime,
        timestamp_field: str = 'created_at'
    ) -> List[ModelType]:
        """Get objects between two dates."""
        if hasattr(self.model, timestamp_field):
            timestamp_column = getattr(self.model, timestamp_field)
            return (
                db.query(self.model)
                .filter(and_(
                    timestamp_column >= start_date,
                    timestamp_column <= end_date
                ))
                .all()
            )
        return []


class StatusMixin:
    """Mixin for repositories that need status-based queries."""
    
    def get_by_status(
        self, 
        db: Session, 
        status: str,
        status_field: str = 'status'
    ) -> List[ModelType]:
        """Get objects by status."""
        if hasattr(self.model, status_field):
            status_column = getattr(self.model, status_field)
            return db.query(self.model).filter(status_column == status).all()
        return []
    
    def get_active(
        self, 
        db: Session,
        active_field: str = 'is_active'
    ) -> List[ModelType]:
        """Get active objects."""
        if hasattr(self.model, active_field):
            active_column = getattr(self.model, active_field)
            return db.query(self.model).filter(active_column == True).all()
        return []


class PriorityMixin:
    """Mixin for repositories that need priority-based queries."""
    
    def get_by_priority_order(
        self,
        db: Session,
        priority_field: str = 'priority',
        limit: int = 10
    ) -> List[ModelType]:
        """Get objects ordered by priority."""
        if hasattr(self.model, priority_field):
            priority_column = getattr(self.model, priority_field)
            return (
                db.query(self.model)
                .order_by(desc(priority_column))
                .limit(limit)
                .all()
            )
        return []