class ServiceError(Exception):
    """Base exception for service layer errors"""
    def __init__(self, message: str, code: int = 400, payload: Optional[Dict] = None):
        super().__init__()
        self.message = message
        self.code = code
        self.payload = payload or {}

    def to_dict(self) -> Dict[str, Any]:
        rv = dict(self.payload or {})
        rv['message'] = self.message
        rv['code'] = self.code
        return rv
        
    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


class ValidationError(ServiceError):
    """Raised when input validation fails"""
    def __init__(self, message: str, field: Optional[str] = None, **kwargs):
        super().__init__(message, code=400, **kwargs)
        self.field = field


class NotFoundError(ServiceError):
    """Raised when a requested resource is not found"""
    def __init__(self, resource: str, **kwargs):
        super().__init__(f"{resource} nie znaleziono", code=404, **kwargs)


class ConflictError(ServiceError):
    """Raised when there's a conflict with the current state"""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, code=409, **kwargs)


class UnauthorizedError(ServiceError):
    """Raised when authentication or authorization fails"""
    def __init__(self, message: str = "Brak uprawnień", **kwargs):
        super().__init__(message, code=401, **kwargs)


class ForbiddenError(ServiceError):
    """Raised when the operation is forbidden"""
    def __init__(self, message: str = "Brak uprawnień do wykonania tej operacji", **kwargs):
        super().__init__(message, code=403, **kwargs)


class ExternalServiceError(ServiceError):
    """Raised when an external service fails"""
    def __init__(self, service_name: str, **kwargs):
        super().__init__(
            f"Błąd połączenia z usługą {service_name}", 
            code=502,  # Bad Gateway
            **kwargs
        )


class DatabaseError(ServiceError):
    """Raised when there's a database error"""
    def __init__(self, message: str = "Błąd bazy danych", **kwargs):
        super().__init__(message, code=500, **kwargs)
