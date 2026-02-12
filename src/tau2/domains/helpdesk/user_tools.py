"""Employee-side tools for the IT helpdesk domain.

These simulate actions an employee can take on their own workstation,
following the same pattern as telecom user_tools.py.
"""

from typing import Optional

from tau2.domains.helpdesk.user_data_model import HelpdeskUserDB, ServiceLoginResult
from tau2.environment.toolkit import ToolKitBase, ToolType, is_tool


class HelpdeskUserTools(ToolKitBase):
    """Employee-side tools for diagnosing and troubleshooting IT issues."""

    db: HelpdeskUserDB

    def __init__(self, db: HelpdeskUserDB) -> None:
        super().__init__(db)

    @property
    def workstation(self):
        return self.db.workstation

    @property
    def surroundings(self):
        return self.db.surroundings

    # ── READ tools ────────────────────────────────────────────────────────

    @is_tool(ToolType.READ)
    def check_internet_connection(self) -> str:
        """Test your internet connectivity. Shows whether you can reach
        external websites and your current connection status."""
        if self.workstation.internet_connected:
            return "Internet connection is working. You can reach external websites."
        return "Internet connection is NOT working. Cannot reach external websites."

    @is_tool(ToolType.READ)
    def check_vpn_connection(self) -> str:
        """Check your VPN connection status. Shows whether you are connected
        to the corporate VPN and any error messages."""
        if self.workstation.vpn_connected:
            return "VPN is connected. You have access to internal resources."
        if self.workstation.vpn_error:
            return f"VPN is NOT connected. Error: {self.workstation.vpn_error}"
        return "VPN is NOT connected."

    @is_tool(ToolType.READ)
    def check_installed_software(self) -> str:
        """List all software currently installed on your workstation,
        along with version numbers."""
        if not self.workstation.installed_software:
            return "No software is installed on this workstation."
        lines = ["Installed software:"]
        for name, version in sorted(self.workstation.installed_software.items()):
            lines.append(f"  - {name} v{version}")
        return "\n".join(lines)

    @is_tool(ToolType.READ)
    def attempt_login(self, service: str) -> str:
        """Try logging into a specific service to check if your credentials work.

        Args:
            service: The name of the service to try logging into
                (e.g., 'email', 'jira', 'confluence', 'github', 'vpn_portal')

        Returns:
            Login result message
        """
        result = self._attempt_login(service)
        if result.success:
            return f"Login to '{service}' succeeded."
        return f"Login to '{service}' failed. Error: {result.error_message}"

    def _attempt_login(self, service: str) -> ServiceLoginResult:
        svc_lower = service.lower()
        status = self.workstation.service_statuses.get(svc_lower)

        if status is None:
            return ServiceLoginResult(
                service=service,
                success=False,
                error_message=f"Service '{service}' not recognized.",
            )

        if self.surroundings.account_locked:
            return ServiceLoginResult(
                service=service,
                success=False,
                error_message="Account is locked. Contact IT support.",
            )

        if self.surroundings.password_expired:
            return ServiceLoginResult(
                service=service,
                success=False,
                error_message="Password has expired. Please reset your password.",
            )

        if status == "accessible":
            return ServiceLoginResult(service=service, success=True)

        return ServiceLoginResult(
            service=service,
            success=False,
            error_message=f"Service returned status: {status}",
        )

    # ── WRITE tools ───────────────────────────────────────────────────────

    @is_tool(ToolType.WRITE)
    def restart_device(self) -> str:
        """Restart your workstation. This can resolve many temporary issues
        like frozen applications or stale network connections."""
        self.workstation.needs_restart = False
        self.workstation.browser_cache_size_mb = 0.0
        return (
            "Device is restarting... Device has restarted successfully. "
            "All applications have been refreshed."
        )

    @is_tool(ToolType.WRITE)
    def clear_browser_cache(self) -> str:
        """Clear your web browser's cache. This can fix issues with
        web applications loading incorrectly or showing outdated content."""
        old_size = self.workstation.browser_cache_size_mb
        self.workstation.browser_cache_size_mb = 0.0
        return (
            f"Browser cache cleared successfully. "
            f"Freed {old_size:.0f} MB of cached data."
        )

    @is_tool(ToolType.WRITE)
    def reconnect_vpn(self) -> str:
        """Disconnect and reconnect to the corporate VPN. This can resolve
        VPN connectivity issues."""
        result = self._reconnect_vpn()
        return result

    def _reconnect_vpn(self) -> str:
        # If internet isn't working, VPN can't connect
        if not self.workstation.internet_connected:
            self.workstation.vpn_connected = False
            self.workstation.vpn_error = "No internet connection"
            return "VPN reconnection failed. No internet connection available."

        # If there's a persistent VPN error (like certificate expired),
        # reconnect won't fix it
        if (
            self.workstation.vpn_error
            and "certificate" in self.workstation.vpn_error.lower()
        ):
            self.workstation.vpn_connected = False
            return (
                f"VPN reconnection failed. "
                f"Persistent error: {self.workstation.vpn_error}"
            )

        # If there's a firewall block, reconnect won't fix it
        if (
            self.workstation.vpn_error
            and "firewall" in self.workstation.vpn_error.lower()
        ):
            self.workstation.vpn_connected = False
            return (
                f"VPN reconnection failed. "
                f"Persistent error: {self.workstation.vpn_error}"
            )

        # Otherwise reconnect succeeds
        self.workstation.vpn_connected = True
        self.workstation.vpn_error = None
        return (
            "VPN reconnected successfully. You now have access to internal resources."
        )

    # ── Setup / break methods (not exposed as tools) ──────────────────────

    def set_employee_info(
        self,
        name: str,
        email: str,
        employee_id: Optional[str] = None,
    ) -> None:
        self.surroundings.employee_name = name
        self.surroundings.employee_email = email
        self.surroundings.employee_id = employee_id

    def break_internet(self) -> str:
        self.workstation.internet_connected = False
        self.workstation.vpn_connected = False
        return "Internet connection broken."

    def break_vpn(self, error: str = "Connection timed out") -> str:
        self.workstation.vpn_connected = False
        self.workstation.vpn_error = error
        return f"VPN broken with error: {error}"

    def lock_account(self) -> str:
        self.surroundings.account_locked = True
        return "Account locked."

    def expire_password(self) -> str:
        self.surroundings.password_expired = True
        return "Password expired."

    def block_service(self, service: str, status: str = "access_denied") -> str:
        self.workstation.service_statuses[service.lower()] = status
        return f"Service '{service}' blocked with status: {status}"

    # ── Assertion helpers ─────────────────────────────────────────────────

    def assert_vpn_connected(self, expected: bool) -> bool:
        return self.workstation.vpn_connected == expected

    def assert_internet_connected(self, expected: bool) -> bool:
        return self.workstation.internet_connected == expected

    def assert_account_locked(self, expected: bool) -> bool:
        return self.surroundings.account_locked == expected

    def assert_service_accessible(self, service: str, expected: bool) -> bool:
        status = self.workstation.service_statuses.get(service.lower())
        is_accessible = status == "accessible"
        return is_accessible == expected

    def assert_browser_cache_cleared(self) -> bool:
        return self.workstation.browser_cache_size_mb == 0.0
