"""
Module for managing VM console operations.
"""

import logging
from typing import Dict, Any

class VMConsoleManager:
    """Manager class for VM console operations."""

    def __init__(self, proxmox_api):
        """Initialize the VM console manager.

        Args:
            proxmox_api: Initialized ProxmoxAPI instance
        """
        self.proxmox = proxmox_api
        self.logger = logging.getLogger("proxmox-mcp.vm-console")

    async def execute_command(self, node: str, vmid: str, command: str) -> Dict[str, Any]:
        """Execute a command in a VM's console.

        Args:
            node: Name of the node where VM is running
            vmid: ID of the VM
            command: Command to execute

        Returns:
            Dictionary containing command output and status

        Raises:
            ValueError: If VM is not found or not running
            RuntimeError: If command execution fails
        """
        try:
            # Verify VM exists and is running
            vm_status = self.proxmox.nodes(node).qemu(vmid).status.current.get()
            if vm_status["status"] != "running":
                self.logger.error(f"Failed to execute command on VM {vmid}: VM is not running")
                raise ValueError(f"VM {vmid} on node {node} is not running")

            # Get VM's console
            self.logger.info(f"Executing command on VM {vmid} (node: {node}): {command}")
            
            # Get the API endpoint
            # Use the guest agent exec endpoint
            endpoint = self.proxmox.nodes(node).qemu(vmid).agent
            self.logger.debug(f"Using API endpoint: {endpoint}")
            
            # Execute the command using two-step process
            try:
                # Start command execution
                self.logger.info("Starting command execution...")
                try:
                    print(f"Executing command via agent: {command}")
                    exec_result = endpoint("exec").post(command=command)
                    print(f"Raw exec response: {exec_result}")
                    self.logger.info(f"Command started with result: {exec_result}")
                except Exception as e:
                    self.logger.error(f"Failed to start command: {str(e)}")
                    raise RuntimeError(f"Failed to start command: {str(e)}")

                if 'pid' not in exec_result:
                    raise RuntimeError("No PID returned from command execution")

                pid = exec_result['pid']
                self.logger.info(f"Waiting for command completion (PID: {pid})...")

                # Add a small delay to allow command to complete
                import asyncio
                await asyncio.sleep(1)

                # Get command output using exec-status
                try:
                    print(f"Getting status for PID {pid}...")
                    console = endpoint("exec-status").get(pid=pid)
                    print(f"Raw exec-status response: {console}")
                    if not console:
                        raise RuntimeError("No response from exec-status")
                except Exception as e:
                    self.logger.error(f"Failed to get command status: {str(e)}")
                    raise RuntimeError(f"Failed to get command status: {str(e)}")
                self.logger.info(f"Command completed with status: {console}")
                print(f"Command completed with status: {console}")
            except Exception as e:
                self.logger.error(f"API call failed: {str(e)}")
                print(f"API call error: {str(e)}")  # Print error for immediate feedback
                raise RuntimeError(f"API call failed: {str(e)}")
            self.logger.info(f"Raw API response type: {type(console)}")
            self.logger.info(f"Raw API response: {console}")
            print(f"Raw API response: {console}")  # Print to stdout for immediate feedback
            
            # Handle different response structures
            if isinstance(console, dict):
                # Handle exec-status response format
                output = console.get("out-data", "")
                error = console.get("err-data", "")
                exit_code = console.get("exitcode", 0)
                exited = console.get("exited", 0)
                
                if not exited:
                    self.logger.warning("Command may not have completed")
            else:
                # Some versions might return data differently
                self.logger.debug(f"Unexpected response type: {type(console)}")
                output = str(console)
                error = ""
                exit_code = 0
            
            self.logger.debug(f"Processed output: {output}")
            self.logger.debug(f"Processed error: {error}")
            self.logger.debug(f"Processed exit code: {exit_code}")
            
            self.logger.debug(f"Executed command '{command}' on VM {vmid} (node: {node})")

            return {
                "success": True,
                "output": output,
                "error": error,
                "exit_code": exit_code
            }

        except ValueError:
            # Re-raise ValueError for VM not running
            raise
        except Exception as e:
            self.logger.error(f"Failed to execute command on VM {vmid}: {str(e)}")
            if "not found" in str(e).lower():
                raise ValueError(f"VM {vmid} not found on node {node}")
            raise RuntimeError(f"Failed to execute command: {str(e)}")
