class WorkflowError(Exception):
    """Base class for errors exposed to Step Functions by stable name."""


class AgentThrottledError(WorkflowError):
    pass


class AgentTimeoutError(WorkflowError):
    pass


class InvalidAgentResponseError(WorkflowError):
    pass


class AgentAccessDeniedError(WorkflowError):
    pass


class AgentServiceError(WorkflowError):
    pass
