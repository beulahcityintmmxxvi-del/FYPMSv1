class AppError(Exception):
    """Base application exception."""


class ValidationError(AppError):
    """Raised when data validation fails."""


class AuthenticationError(AppError):
    """Raised when login/reset authentication fails."""


class WorkflowError(AppError):
    """Raised when workflow sequencing is violated."""


class FileError(AppError):
    """Raised when file validation or storage fails."""


class PlagiarismError(AppError):
    """Raised when plagiarism analysis fails."""