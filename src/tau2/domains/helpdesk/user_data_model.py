from typing import Any, Dict, Optional

from pydantic import Field

from tau2.environment.db import DB
from tau2.utils.pydantic_utils import BaseModelNoExtra


class ServiceLoginResult(BaseModelNoExtra):
    """Result of attempting to log into a service."""

    service: str = Field(description="Name of the service")
    success: bool = Field(description="Whether login succeeded")
    error_message: Optional[str] = Field(
        None, description="Error message if login failed"
    )


class MockWorkstation(BaseModelNoExtra):
    """Data model representing the state of an employee's workstation."""

    internet_connected: bool = Field(
        True, description="Whether the workstation has internet connectivity"
    )
    vpn_connected: bool = Field(
        False, description="Whether the VPN is currently connected"
    )
    vpn_error: Optional[str] = Field(
        None, description="VPN error message if connection failed"
    )
    installed_software: Dict[str, str] = Field(
        default_factory=lambda: {
            "Chrome": "120.0",
            "Outlook": "16.0",
            "Teams": "1.6",
            "Slack": "4.35",
        },
        description="Software installed on the workstation (name -> version)",
    )
    browser_cache_size_mb: float = Field(250.0, description="Browser cache size in MB")
    needs_restart: bool = Field(
        False, description="Whether the workstation needs a restart"
    )
    last_restart: Optional[str] = Field(
        None, description="Date of last restart (YYYY-MM-DD)"
    )
    service_statuses: Dict[str, str] = Field(
        default_factory=lambda: {
            "email": "accessible",
            "jira": "accessible",
            "confluence": "accessible",
            "github": "accessible",
            "vpn_portal": "accessible",
        },
        description="Status of various services (service -> status)",
    )


class UserSurroundings(BaseModelNoExtra):
    """Context about the employee's situation."""

    employee_name: Optional[str] = Field(None, description="Name of the employee")
    employee_email: Optional[str] = Field(None, description="Email of the employee")
    employee_id: Optional[str] = Field(None, description="Employee ID")
    is_remote: bool = Field(
        False, description="Whether the employee is working remotely"
    )
    account_locked: bool = Field(
        False, description="Whether the employee's account is locked"
    )
    password_expired: bool = Field(
        False, description="Whether the employee's password has expired"
    )


class HelpdeskUserDB(DB):
    """User-side database for IT helpdesk domain."""

    workstation: MockWorkstation = Field(
        default_factory=MockWorkstation,
        description="Employee's workstation state",
    )
    surroundings: UserSurroundings = Field(
        default_factory=UserSurroundings,
        description="Employee's context",
    )

    def update_workstation(self, update_data: Dict[str, Any]) -> None:
        """Update the workstation state."""
        from tau2.utils.pydantic_utils import update_pydantic_model_with_dict

        self.workstation = update_pydantic_model_with_dict(
            self.workstation, update_data
        )
