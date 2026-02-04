import hashlib

def calculate_arc_id(identifier: str, rdi: str) -> str:
    """Generate a unique ARC ID based on the identifier and RDI.

    Args:
        identifier: The identifier from the ARC (e.g. from ISA object).
        rdi: The Research Data Infrastructure identifier.

    Returns:
        A SHA-256 hash of "identifier:rdi".
    """
    input_str = f"{identifier}:{rdi}"
    return hashlib.sha256(input_str.encode("utf-8")).hexdigest()
