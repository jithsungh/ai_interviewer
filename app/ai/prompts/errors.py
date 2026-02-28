"""
Prompt Layer Errors

Extends shared error hierarchy with prompt-specific error types.
All errors inherit from app.shared.errors.BaseError.
"""

from typing import Any, Dict, List, Optional

from app.shared.errors import BaseError, NotFoundError, ValidationError


class PromptNotFoundError(NotFoundError):
    """
    No active prompt template found for the given type and scope.

    Raised when:
    - No active prompt exists for prompt_type + organization_id
    - Fallback to global also fails
    - prompt_type not recognized in database
    """

    def __init__(
        self,
        prompt_type: str,
        organization_id: Optional[int] = None,
        request_id: Optional[str] = None,
    ):
        scope_desc = (
            f"organization_id={organization_id}"
            if organization_id
            else "global"
        )
        super().__init__(
            resource_type="PromptTemplate",
            resource_id=f"{prompt_type}/{scope_desc}",
            request_id=request_id,
        )
        # Attach structured metadata
        self.metadata.update({
            "prompt_type": prompt_type,
            "organization_id": organization_id,
        })


class VariableMissingError(ValidationError):
    """
    One or more required template variables were not provided.

    Raised when render_prompt() is called with an incomplete variables dict
    that omits variables present in the template.
    """

    def __init__(
        self,
        missing_variables: List[str],
        prompt_type: Optional[str] = None,
        request_id: Optional[str] = None,
    ):
        msg = f"Missing template variables: {', '.join(sorted(missing_variables))}"
        super().__init__(
            message=msg,
            field="variables",
            request_id=request_id,
            metadata={
                "missing_variables": sorted(missing_variables),
                "prompt_type": prompt_type,
            },
        )
        self.missing_variables = missing_variables


class TemplateSyntaxError(ValidationError):
    """
    Template contains invalid syntax.

    Raised when:
    - Unclosed {{ or }}
    - Nested variable references {{user_{{type}}}}
    - Empty variable names {{}}
    """

    def __init__(
        self,
        message: str,
        position: Optional[int] = None,
        template_snippet: Optional[str] = None,
        request_id: Optional[str] = None,
    ):
        metadata: Dict[str, Any] = {}
        if position is not None:
            metadata["position"] = position
        if template_snippet is not None:
            metadata["template_snippet"] = template_snippet

        super().__init__(
            message=f"Template syntax error: {message}",
            field="template",
            request_id=request_id,
            metadata=metadata,
        )
