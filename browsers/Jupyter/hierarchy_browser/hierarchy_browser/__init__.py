from ._version import __version__


def _jupyter_labextension_paths():
    return [{
        "src": "labextension",
        "dest": "hierarchy-browser"
    }]


def _jupyter_server_extension_points():
    """Entry point for the server extension."""
    return [{"module": "hierarchy_browser"}]


def _load_jupyter_server_extension(server_app):
    """Called when the extension is loaded."""
    from .handlers import setup_handlers
    
    # Setup the API handlers
    print("Hierarchy Browser: Setting up server extension handlers...")
    setup_handlers(server_app.web_app)
    
    print("Hierarchy Browser server extension loaded successfully!")
