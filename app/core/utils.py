def use_flow(file_path: str):
    """
    A python decorator that links a route to a Markdown flow checklist.
    Use Ctrl+Click on the file_path in your IDE to open the logic.
    """

    def decorator(func):
        func._flow_doc = file_path  # Stored for reference
        return func

    return decorator
