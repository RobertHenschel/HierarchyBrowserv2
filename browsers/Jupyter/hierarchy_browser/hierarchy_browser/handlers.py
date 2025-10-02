#!/usr/bin/env python3
"""
Server handlers for the Hierarchy Browser JupyterLab extension.
"""

import json
import logging
import socket
from typing import Dict, Any, Optional

from jupyter_server.base.handlers import APIHandler
from jupyter_server.utils import url_path_join
import tornado

# Configure logging
logger = logging.getLogger(__name__)


class ProviderConnectionError(Exception):
    """Exception raised when provider connection fails."""
    pass


class ProviderClient:
    """Client for connecting to hierarchy browser providers."""
    
    # Constants
    DEFAULT_HOST = "127.0.0.1"
    DEFAULT_PORT = 9100
    DEFAULT_TIMEOUT = 10
    BUFFER_SIZE = 4096
    MESSAGE_TERMINATOR = b"\n"
    
    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, timeout: int = DEFAULT_TIMEOUT):
        self.host = host
        self.port = port
        self.timeout = timeout
    
    def _make_request(self, method: str, **kwargs) -> Dict[str, Any]:
        """
        Make a generic request to the provider.
        
        Args:
            method: The provider method to call
            **kwargs: Additional parameters for the method
            
        Returns:
            Response dictionary from the provider
            
        Raises:
            ProviderConnectionError: If connection or communication fails
        """
        payload = {"method": method, **kwargs}
        message = json.dumps(payload, separators=(",", ":")) + "\n"
        
        try:
            return self._send_message(message)
        except Exception as e:
            error_msg = f"Failed to connect to provider at {self.host}:{self.port}: {str(e)}"
            logger.error(error_msg)
            return {"error": error_msg}
    
    def _send_message(self, message: str) -> Dict[str, Any]:
        """
        Send a message to the provider and receive response.
        
        Args:
            message: JSON message to send
            
        Returns:
            Parsed JSON response
            
        Raises:
            ProviderConnectionError: If communication fails
        """
        try:
            with socket.create_connection((self.host, self.port), timeout=self.timeout) as sock:
                sock.sendall(message.encode("utf-8"))
                response_data = self._receive_response(sock)
                
            return json.loads(response_data) if response_data else {}
            
        except (socket.error, ConnectionError, OSError) as e:
            raise ProviderConnectionError(f"Network error: {str(e)}") from e
        except json.JSONDecodeError as e:
            raise ProviderConnectionError(f"Invalid JSON response: {str(e)}") from e
    
    def _receive_response(self, sock: socket.socket) -> str:
        """
        Receive a complete response from the socket.
        
        Args:
            sock: Connected socket
            
        Returns:
            Complete response string
            
        Raises:
            ProviderConnectionError: If receiving fails
        """
        buffer = b""
        while not buffer.endswith(self.MESSAGE_TERMINATOR):
            chunk = sock.recv(self.BUFFER_SIZE)
            if not chunk:
                break
            buffer += chunk
        
        return buffer.decode("utf-8").strip()
    
    def request_get_info(self) -> Dict[str, Any]:
        """Get provider information including name and available icons."""
        return self._make_request("GetInfo")
    
    def request_get_root_objects(self) -> Dict[str, Any]:
        """Get root objects from the provider."""
        return self._make_request("GetRootObjects")
    
    def request_get_objects(self, object_id: str) -> Dict[str, Any]:
        """
        Get child objects for a specific object ID.
        
        Args:
            object_id: ID of the parent object
            
        Returns:
            Response containing child objects
        """
        return self._make_request("GetObjects", id=object_id)


class HierarchyBrowserHandler(APIHandler):
    """Main API handler for hierarchy browser operations."""

    def initialize(self) -> None:
        """Initialize the handler with provider client."""
        # TODO: Make host and port configurable via settings
        self.client = ProviderClient(
            host=ProviderClient.DEFAULT_HOST,
            port=ProviderClient.DEFAULT_PORT
        )

    @tornado.web.authenticated
    def get(self) -> None:
        """
        Handle GET requests for provider operations.
        
        Query parameters:
            action: The action to perform ('info', 'root', 'objects')
            id: Object ID (required for 'objects' action)
        """
        action = self.get_query_argument("action", default="info")
        
        try:
            result = self._handle_action(action)
            self.finish(json.dumps(result))
            
        except Exception as e:
            logger.error(f"Handler error for action '{action}': {str(e)}")
            self.set_status(500)
            self.finish(json.dumps({"error": f"Server error: {str(e)}"}))
    
    def _handle_action(self, action: str) -> Dict[str, Any]:
        """
        Handle specific provider actions.
        
        Args:
            action: The action to perform
            
        Returns:
            Provider response
            
        Raises:
            ValueError: For unknown actions or missing parameters
        """
        if action == "info":
            return self.client.request_get_info()
        
        elif action == "root":
            return self.client.request_get_root_objects()
        
        elif action == "objects":
            object_id = self.get_query_argument("id", default=None)
            if not object_id:
                raise ValueError("Missing required 'id' parameter for objects action")
            return self.client.request_get_objects(object_id)
        
        else:
            raise ValueError(f"Unknown action: {action}")


def setup_handlers(web_app) -> None:
    """
    Setup the API handlers for the hierarchy browser extension.
    
    Args:
        web_app: The JupyterLab web application instance
    """
    host_pattern = ".*$"
    base_url = web_app.settings.get("base_url", "/")
    
    # Register API handler
    route_pattern = url_path_join(base_url, "hierarchy-browser", "api")
    handlers = [(route_pattern, HierarchyBrowserHandler)]
    web_app.add_handlers(host_pattern, handlers)
    
    logger.info(f"Hierarchy Browser: Registered API handler at {route_pattern}")
