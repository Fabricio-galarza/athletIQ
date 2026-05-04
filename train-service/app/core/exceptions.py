"""
Custom exceptions for Train service
"""


class TrainServiceException(Exception):
    """Base exception for Train service"""
    pass


class ValidationError(TrainServiceException):
    """Raised when form validation fails"""
    
    def __init__(self, message: str, details: dict = None):
        self.message = message
        self.details = details or {}
        super().__init__(message)


class NotFoundError(TrainServiceException):
    """Raised when a resource is not found"""
    
    def __init__(self, entity: str, entity_id: str):
        self.message = f"{entity} with id {entity_id} not found"
        super().__init__(self.message)