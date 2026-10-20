"""Repository-layer errors shared by agent persistence modules."""


class CaseBusyError(RuntimeError):
    """Raised when another synchronous HTTP request owns a case run."""


class CaseVersionConflictError(RuntimeError):
    """Raised when a queue mutation uses a stale case version."""


class CaseAlreadyClaimedError(RuntimeError):
    """Raised when another actor owns an operational case."""


class CaseReleaseForbiddenError(RuntimeError):
    """Raised when the current case lifecycle does not permit release."""


class FindingResolutionConflictError(RuntimeError):
    """Raised when a finding cannot be resolved during case execution."""


class AnalysisStaleError(RuntimeError):
    """Raised when a live finding changed while a recommendation was computed."""


class AnalysisForbiddenError(RuntimeError):
    """Raised when a case cannot enter the readiness analysis workflow."""


class ReadinessConfirmationError(RuntimeError):
    """Raised when an operational recommendation cannot be frozen or decided."""
