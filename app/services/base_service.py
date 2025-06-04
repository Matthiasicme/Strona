from datetime import datetime
from typing import Optional, Dict, Any, List, TypeVar, Generic, Type, Tuple, Union, cast
from sqlalchemy.orm import Session, Query
from sqlalchemy.orm.attributes import InstrumentedAttribute
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import db
from exceptions import (
    ServiceError, 
    ValidationError, 
    NotFoundError, 
    ConflictError,
    DatabaseError
)

T = TypeVar('T', bound=Any)
ModelType = TypeVar('ModelType')
CreateSchemaType = Dict[str, Any]
UpdateSchemaType = Dict[str, Any]

class BaseService(Generic[ModelType]):
    """
    Base service class with common CRUD operations and advanced querying capabilities.
    
    This class provides a foundation for service layer classes by implementing
    common database operations in a type-safe and consistent way.
    """
    
    def __init__(self, model: Type[ModelType], db_session: Optional[Session] = None):
        """
        Initialize the service with a SQLAlchemy model.
        
        Args:
            model: The SQLAlchemy model class to operate on
            db_session: Optional database session (uses Flask-SQLAlchemy session by default)
        """
        self.model = model
        self.db_session = db_session or db.session
    
    def get_query(self) -> Query[ModelType]:
        """Get the base query for this model"""
        return self.db_session.query(self.model)
    
    def get(self, id: int, raise_if_not_found: bool = False) -> Optional[ModelType]:
        """
        Get a single record by ID.
        
        Args:
            id: The ID of the record to retrieve
            raise_if_not_found: If True, raises NotFoundError when record not found
            
        Returns:
            The model instance if found, None otherwise
            
        Raises:
            NotFoundError: If record not found and raise_if_not_found is True
        """
        instance = self.get_query().get(id)
        if instance is None and raise_if_not_found:
            raise NotFoundError(resource=self.model.__name__.lower())
        return instance
    
    def get_by(self, **filters: Any) -> Optional[ModelType]:
        """
        Get a single record by filters.
        
        Args:
            **filters: Filters to apply (e.g., name='test', active=True)
            
        Returns:
            The first matching model instance or None if not found
        """
        return self.get_query().filter_by(**filters).first()
    
    def get_or_create(
        self, 
        defaults: Optional[Dict[str, Any]] = None, 
        **filters: Any
    ) -> Tuple[ModelType, bool]:
        """
        Get an existing record or create it if it doesn't exist.
        
        Args:
            defaults: Default values to use when creating a new record
            **filters: Filters to find an existing record
            
        Returns:
            A tuple of (instance, created) where created is a boolean
            indicating whether the object was created
        """
        instance = self.get_by(**filters)
        if instance:
            return instance, False
            
        data = {**filters, **(defaults or {})}
        return self.create(**data), True
    
    def get_all(
        self, 
        *, 
        skip: int = 0, 
        limit: int = 100,
        order_by: Optional[str] = None,
        order: str = 'asc',
        **filters: Any
    ) -> Tuple[List[ModelType], int]:
        """
        Get multiple records with optional filtering and pagination.
        
        Args:
            skip: Number of records to skip (for pagination)
            limit: Maximum number of records to return
            order_by: Field to order by
            order: Sort order ('asc' or 'desc')
            **filters: Filters to apply
            
        Returns:
            A tuple of (results, total_count)
        """
        query = self.get_query()
        
        # Apply filters
        for field, value in filters.items():
            if hasattr(self.model, field):
                field_attr: InstrumentedAttribute = getattr(self.model, field)
                if isinstance(value, (list, tuple)):
                    query = query.filter(field_attr.in_(value))
                else:
                    query = query.filter(field_attr == value)
        
        # Get total count before pagination
        total = query.count()
        
        # Apply ordering
        if order_by and hasattr(self.model, order_by):
            order_field = getattr(self.model, order_by)
            if order.lower() == 'desc':
                query = query.order_by(order_field.desc())
            else:
                query = query.order_by(order_field)
        
        # Apply pagination
        if limit > 0:
            query = query.offset(skip).limit(limit)
        
        return query.all(), total
    
    def create(self, **data: Any) -> ModelType:
        """
        Create a new record.
        
        Args:
            **data: Data for the new record
            
        Returns:
            The created model instance
            
        Raises:
            ValidationError: If data validation fails
            DatabaseError: If there's a database error
        """
        try:
            instance = self.model(**data)
            self.db_session.add(instance)
            self.db_session.commit()
            self.db_session.refresh(instance)
            return instance
            
        except Exception as e:
            self.db_session.rollback()
            raise DatabaseError(f"Error creating {self.model.__name__.lower()}: {str(e)}")
    
    def update(self, id: int, **data: Any) -> Optional[ModelType]:
        """
        Update an existing record.
        
        Args:
            id: ID of the record to update
            **data: Data to update
            
        Returns:
            The updated model instance or None if not found
            
        Raises:
            NotFoundError: If record not found and raise_if_not_found is True
            ValidationError: If data validation fails
            DatabaseError: If there's a database error
        """
        instance = self.get(id, raise_if_not_found=True)
        if not instance:
            return None
            
        try:
            for key, value in data.items():
                if hasattr(instance, key):
                    setattr(instance, key, value)
            
            # Update modification timestamp if the field exists
            if hasattr(instance, 'data_modyfikacji'):
                instance.data_modyfikacji = datetime.utcnow()
                
            self.db_session.commit()
            self.db_session.refresh(instance)
            return instance
            
        except Exception as e:
            self.db_session.rollback()
            raise DatabaseError(f"Error updating {self.model.__name__.lower()}: {str(e)}")
    
    def delete(self, id: int) -> bool:
        """
        Delete a record by ID.
        
        Args:
            id: ID of the record to delete
            
        Returns:
            True if the record was deleted, False if not found
            
        Raises:
            DatabaseError: If there's a database error
        """
        instance = self.get(id)
        if not instance:
            return False
            
        try:
            self.db_session.delete(instance)
            self.db_session.commit()
            return True
            
        except Exception as e:
            self.db_session.rollback()
            raise DatabaseError(f"Error deleting {self.model.__name__.lower()}: {str(e)}")
    
    def exists(self, **filters: Any) -> bool:
        """
        Check if a record exists with the given filters.
        
        Args:
            **filters: Filters to apply
            
        Returns:
            True if a matching record exists, False otherwise
        """
        return self.get_query().filter_by(**filters).first() is not None
    
    def count(self, **filters: Any) -> int:
        """
        Count records matching the given filters.
        
        Args:
            **filters: Filters to apply
            
        Returns:
            Number of matching records
        """
        query = self.get_query()
        for field, value in filters.items():
            if hasattr(self.model, field):
                field_attr = getattr(self.model, field)
                query = query.filter(field_attr == value)
        return query.count()
    
    def bulk_create(self, items: List[Dict[str, Any]]) -> List[ModelType]:
        """
        Create multiple records in a single transaction.
        
        Args:
            items: List of dictionaries with data for new records
            
        Returns:
            List of created model instances
            
        Raises:
            DatabaseError: If there's a database error
        """
        try:
            instances = [self.model(**item) for item in items]
            self.db_session.bulk_save_objects(instances)
            self.db_session.commit()
            return instances
            
        except Exception as e:
            self.db_session.rollback()
            raise DatabaseError(f"Error in bulk create: {str(e)}")
    
    def bulk_update(self, model_instances: List[ModelType]) -> None:
        """
        Update multiple records in a single transaction.
        
        Args:
            model_instances: List of model instances to update
            
        Raises:
            DatabaseError: If there's a database error
        """
        try:
            for instance in model_instances:
                if hasattr(instance, 'data_modyfikacji'):
                    instance.data_modyfikacji = datetime.utcnow()
            self.db_session.bulk_save_objects(model_instances)
            self.db_session.commit()
            
        except Exception as e:
            self.db_session.rollback()
            raise DatabaseError(f"Error in bulk update: {str(e)}")
