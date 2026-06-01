"""
Kill Switch - Blocks all traffic when proxy disconnects unexpectedly

Uses iptables rules to block all outgoing traffic except xray-core process.
"""

import asyncio
import time
from typing import Dict, Any, Optional, List


class KillSwitch:
    """
    Manages kill switch functionality using iptables.

    When activated, blocks all outgoing traffic except xray-core process.
    Rules are applied in this order:
      1. ACCEPT on loopback (lo) — keeps IPC / Decky communication alive
      2. ACCEPT for xray-core PID — allows proxy traffic
      3. DROP everything else — leak protection
    """

    def __init__(self):
        """Initialize KillSwitch."""
        self.is_active: bool = False
        self.activated_at: Optional[float] = None
        self.rule_ids: List[str] = []
        self.xray_process_id: Optional[int] = None
        # Maps rule_id → the iptables command list that was applied (with -A).
        # Used by _remove_rule to replay the command with -D.
        self._applied_rules: Dict[str, List[str]] = {}

    async def activate(self, xray_process_id: int) -> Dict[str, Any]:
        """
        Activate kill switch - block all traffic except xray-core.

        Args:
            xray_process_id: Process ID of xray-core to allow

        Returns:
            Dictionary with activation result
        """
        try:
            if self.is_active:
                # Already active, just update process ID
                self.xray_process_id = xray_process_id
                return {"success": True, "message": "Kill switch already active"}

            self.xray_process_id = xray_process_id
            applied: List[str] = []

            # Rule 1: Allow loopback traffic (lo) — MUST come before DROP
            # Without this, Decky Loader IPC, localhost web servers, and
            # inter-process communication would be killed immediately.
            rule_lo_cmd = ["iptables", "-A", "OUTPUT", "-o", "lo", "-j", "ACCEPT"]
            rule_lo_result = await self._apply_rule(rule_lo_cmd, "kill-switch-allow-lo")

            if not rule_lo_result["success"]:
                return {
                    "success": False,
                    "error": f"Failed to apply loopback rule: {rule_lo_result.get('error')}",
                    "errorCode": "IPTABLES_FAILED",
                }
            applied.append("kill-switch-allow-lo")

            # Rule 2: Allow traffic from root UID (xray-core runs as root,
            # spawned by Decky Loader).  --pid-owner is removed from modern
            # kernels (including SteamOS 3.x); --uid-owner is universal.
            rule_xray_cmd = [
                "iptables",
                "-A",
                "OUTPUT",
                "-m",
                "owner",
                "--uid-owner",
                "0",
                "-j",
                "ACCEPT",
            ]
            rule_xray_id = f"xray-allow-root-uid"
            rule_xray_result = await self._apply_rule(rule_xray_cmd, rule_xray_id)

            if not rule_xray_result["success"]:
                # Rollback loopback rule
                for rid in reversed(applied):
                    await self._remove_rule(rid)
                return {
                    "success": False,
                    "error": f"Failed to apply allow rule: {rule_xray_result.get('error')}",
                    "errorCode": "IPTABLES_FAILED",
                }
            applied.append(rule_xray_id)

            # Rule 3: Block all other traffic
            rule_drop_cmd = ["iptables", "-A", "OUTPUT", "-j", "DROP"]
            rule_drop_result = await self._apply_rule(
                rule_drop_cmd, "kill-switch-block-all"
            )

            if not rule_drop_result["success"]:
                # Rollback previously applied rules
                for rid in reversed(applied):
                    await self._remove_rule(rid)
                return {
                    "success": False,
                    "error": f"Failed to apply block rule: {rule_drop_result.get('error')}",
                    "errorCode": "IPTABLES_FAILED",
                }
            applied.append("kill-switch-block-all")

            self.is_active = True
            self.activated_at = time.time()
            self.rule_ids = applied

            return {"success": True, "activatedAt": int(self.activated_at)}

        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to activate kill switch: {str(e)}",
                "errorCode": "KILL_SWITCH_ERROR",
            }

    async def deactivate(self) -> Dict[str, Any]:
        """
        Deactivate kill switch - remove iptables rules.

        Returns:
            Dictionary with deactivation result
        """
        try:
            if not self.is_active:
                return {"success": True, "message": "Kill switch not active"}

            # Remove rules in reverse order (DROP first, then ACCEPT rules)
            errors = []
            for rule_id in reversed(self.rule_ids):
                result = await self._remove_rule(rule_id)
                if not result["success"]:
                    errors.append(f"{rule_id}: {result.get('error', 'unknown')}")

            self.is_active = False
            self.activated_at = None
            self.rule_ids = []
            self.xray_process_id = None
            self._applied_rules.clear()

            if errors:
                return {
                    "success": True,
                    "warnings": errors,
                }

            return {"success": True}

        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to deactivate kill switch: {str(e)}",
                "errorCode": "KILL_SWITCH_ERROR",
            }

    async def _apply_rule(self, command: List[str], rule_id: str) -> Dict[str, Any]:
        """
        Apply an iptables rule.

        Args:
            command: iptables command as list (must use -A for append)
            rule_id: Identifier for the rule

        Returns:
            Dictionary with result
        """
        try:
            process = await asyncio.create_subprocess_exec(
                *command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )

            await process.wait()

            if process.returncode == 0:
                # Store the command so _remove_rule can replay it with -D
                self._applied_rules[rule_id] = list(command)
                return {"success": True, "ruleId": rule_id}
            else:
                stderr = await process.stderr.read()
                error_msg = (
                    stderr.decode("utf-8", errors="ignore")
                    if stderr
                    else "Unknown error"
                )
                return {"success": False, "error": error_msg}

        except FileNotFoundError:
            return {"success": False, "error": "iptables command not found"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _remove_rule(self, rule_id: str) -> Dict[str, Any]:
        """
        Remove an iptables rule by replaying its original command with -D (delete).

        Args:
            rule_id: Identifier for the rule to remove

        Returns:
            Dictionary with result
        """
        try:
            original_cmd = self._applied_rules.get(rule_id)
            if not original_cmd:
                # Rule was never tracked — nothing to remove
                return {"success": True}

            # Build the delete command: replace -A with -D
            delete_cmd = []
            for part in original_cmd:
                if part == "-A":
                    delete_cmd.append("-D")
                else:
                    delete_cmd.append(part)

            process = await asyncio.create_subprocess_exec(
                *delete_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            await process.wait()

            # Clean up tracking regardless of result
            self._applied_rules.pop(rule_id, None)

            if process.returncode == 0:
                return {"success": True}
            else:
                stderr = await process.stderr.read()
                error_msg = (
                    stderr.decode("utf-8", errors="ignore")
                    if stderr
                    else "Unknown error"
                )
                # Don't fail deactivation if a single rule removal fails
                print(f"Warning: Failed to remove iptables rule {rule_id}: {error_msg}")
                return {"success": False, "error": error_msg}

        except Exception as e:
            # Don't fail deactivation if rule removal fails
            # Log the error but continue
            print(f"Warning: Failed to remove iptables rule {rule_id}: {e}")
            return {"success": False, "error": str(e)}

    def get_status(self) -> Dict[str, Any]:
        """
        Get current kill switch status.

        Returns:
            Dictionary with status information
        """
        return {
            "isActive": self.is_active,
            "activatedAt": int(self.activated_at) if self.activated_at else None,
            "processId": self.xray_process_id,
            "ruleIds": self.rule_ids.copy(),
        }
