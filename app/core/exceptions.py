class AppException(Exception):
    """Base application exception."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class TripNotFound(AppException):
    def __init__(self, message: str = "Trip not found"):
        super().__init__(message=message, status_code=404)


class TripNotAwaitingReview(AppException):
    def __init__(self, message: str = "Trip is not awaiting review"):
        super().__init__(message=message, status_code=409)
