def process(data):
    # Validate first
    if not isinstance(data, dict):
        raise ValueError("Expected dict")
    return data
