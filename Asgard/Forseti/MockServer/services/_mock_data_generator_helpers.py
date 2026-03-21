"""
Mock Data Generator Helpers.

Helper functions for MockDataGeneratorService.
"""

import hashlib
import random
import string
import uuid
from datetime import datetime, timedelta
from typing import Any


FIRST_NAMES = [
    "James", "John", "Robert", "Michael", "David", "William", "Richard",
    "Joseph", "Thomas", "Charles", "Mary", "Patricia", "Jennifer", "Linda",
    "Elizabeth", "Barbara", "Susan", "Jessica", "Sarah", "Karen"
]
LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
    "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez",
    "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin"
]
DOMAINS = ["example.com", "test.org", "sample.net", "demo.io", "mock.dev"]
STREET_TYPES = ["St", "Ave", "Blvd", "Dr", "Ln", "Rd", "Way", "Ct"]
CITIES = [
    "New York", "Los Angeles", "Chicago", "Houston", "Phoenix",
    "Philadelphia", "San Antonio", "San Diego", "Dallas", "San Jose"
]
COUNTRIES = ["USA", "Canada", "UK", "Australia", "Germany", "France"]
LOREM_WORDS = [
    "lorem", "ipsum", "dolor", "sit", "amet", "consectetur",
    "adipiscing", "elit", "sed", "do", "eiusmod", "tempor",
    "incididunt", "ut", "labore", "et", "dolore", "magna", "aliqua"
]


def generate_email(rng: random.Random) -> str:
    """Generate a realistic email address."""
    first = rng.choice(FIRST_NAMES).lower()
    last = rng.choice(LAST_NAMES).lower()
    domain = rng.choice(DOMAINS)
    return f"{first}.{last}@{domain}"


def generate_url(rng: random.Random) -> str:
    """Generate a realistic URL."""
    domain = rng.choice(DOMAINS)
    path = "/".join(
        "".join(rng.choices(string.ascii_lowercase, k=6))
        for _ in range(rng.randint(1, 3))
    )
    return f"https://{domain}/{path}"


def generate_phone(rng: random.Random) -> str:
    """Generate a realistic phone number."""
    area = rng.randint(200, 999)
    prefix = rng.randint(200, 999)
    line = rng.randint(1000, 9999)
    return f"+1-{area}-{prefix}-{line}"


def generate_name(rng: random.Random) -> str:
    """Generate a full name."""
    first = rng.choice(FIRST_NAMES)
    last = rng.choice(LAST_NAMES)
    return f"{first} {last}"


def generate_username(rng: random.Random) -> str:
    """Generate a username."""
    first = rng.choice(FIRST_NAMES).lower()
    num = rng.randint(1, 999)
    return f"{first}{num}"


def generate_street(rng: random.Random) -> str:
    """Generate a street address."""
    num = rng.randint(1, 9999)
    name = rng.choice(LAST_NAMES)
    street_type = rng.choice(STREET_TYPES)
    return f"{num} {name} {street_type}"


def generate_address(rng: random.Random) -> str:
    """Generate a full address."""
    street = generate_street(rng)
    city = rng.choice(CITIES)
    country = rng.choice(COUNTRIES)
    return f"{street}, {city}, {country}"


def generate_zip(rng: random.Random) -> str:
    """Generate a ZIP code."""
    return str(rng.randint(10000, 99999))


def generate_date(rng: random.Random) -> str:
    """Generate a random date."""
    days_offset = rng.randint(-365, 365)
    date = datetime.now() + timedelta(days=days_offset)
    return date.strftime("%Y-%m-%d")


def generate_datetime(rng: random.Random) -> str:
    """Generate a random datetime."""
    days_offset = rng.randint(-365, 365)
    hours_offset = rng.randint(0, 23)
    dt = datetime.now() + timedelta(days=days_offset, hours=hours_offset)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def generate_time(rng: random.Random) -> str:
    """Generate a random time."""
    hour = rng.randint(0, 23)
    minute = rng.randint(0, 59)
    second = rng.randint(0, 59)
    return f"{hour:02d}:{minute:02d}:{second:02d}"


def generate_ipv4(rng: random.Random) -> str:
    """Generate a random IPv4 address."""
    return ".".join(str(rng.randint(0, 255)) for _ in range(4))


def generate_ipv6(rng: random.Random) -> str:
    """Generate a random IPv6 address."""
    return ":".join(
        "".join(rng.choices("0123456789abcdef", k=4))
        for _ in range(8)
    )


def generate_password(rng: random.Random) -> str:
    """Generate a random password."""
    chars = string.ascii_letters + string.digits + "!@#$%^&*"
    return "".join(rng.choices(chars, k=16))


def generate_token(rng: random.Random) -> str:
    """Generate a random token."""
    return hashlib.sha256(str(rng.random()).encode()).hexdigest()[:32]


def generate_lorem(rng: random.Random, min_sentences: int, max_sentences: int) -> str:
    """Generate lorem ipsum-style text."""
    sentences = []
    for _ in range(rng.randint(min_sentences, max_sentences)):
        length = rng.randint(5, 12)
        sentence_words = rng.choices(LOREM_WORDS, k=length)
        sentence_words[0] = sentence_words[0].capitalize()
        sentences.append(" ".join(sentence_words) + ".")
    return " ".join(sentences)


def infer_from_property_name(property_name: str, rng: random.Random) -> Any:
    """Infer data type and generate based on property name."""
    name_lower = property_name.lower()
    if any(x in name_lower for x in ["email", "mail"]):
        return generate_email(rng)
    elif any(x in name_lower for x in ["phone", "tel", "mobile"]):
        return generate_phone(rng)
    elif any(x in name_lower for x in ["url", "uri", "link", "href", "website"]):
        return generate_url(rng)
    elif any(x in name_lower for x in ["uuid", "guid", "id"]) and "id" in name_lower:
        return str(uuid.uuid4())
    elif any(x in name_lower for x in ["first_name", "firstname", "given_name"]):
        return rng.choice(FIRST_NAMES)
    elif any(x in name_lower for x in ["last_name", "lastname", "surname", "family_name"]):
        return rng.choice(LAST_NAMES)
    elif "name" in name_lower and "user" in name_lower:
        return generate_username(rng)
    elif "name" in name_lower:
        return generate_name(rng)
    elif any(x in name_lower for x in ["address", "street"]):
        return generate_street(rng)
    elif "city" in name_lower:
        return rng.choice(CITIES)
    elif "country" in name_lower:
        return rng.choice(COUNTRIES)
    elif any(x in name_lower for x in ["zip", "postal"]):
        return generate_zip(rng)
    elif any(x in name_lower for x in ["date", "created", "updated", "timestamp"]):
        return generate_datetime(rng)
    elif any(x in name_lower for x in ["description", "bio", "summary", "about"]):
        return generate_lorem(rng, 2, 4)
    elif any(x in name_lower for x in ["title", "subject", "headline"]):
        return generate_lorem(rng, 1, 1).rstrip(".")
    elif "password" in name_lower:
        return generate_password(rng)
    elif "token" in name_lower:
        return generate_token(rng)
    elif "ip" in name_lower:
        return generate_ipv4(rng)
    return None


def generate_formatted_string(format_type: str, rng: random.Random) -> str:
    """Generate a string based on format type."""
    if format_type == "email":
        return generate_email(rng)
    elif format_type in ("uri", "url"):
        return generate_url(rng)
    elif format_type == "uuid":
        return str(uuid.uuid4())
    elif format_type == "date":
        return generate_date(rng)
    elif format_type == "date-time":
        return generate_datetime(rng)
    elif format_type == "time":
        return generate_time(rng)
    elif format_type == "hostname":
        return rng.choice(DOMAINS)
    elif format_type == "ipv4":
        return generate_ipv4(rng)
    elif format_type == "ipv6":
        return generate_ipv6(rng)
    elif format_type == "phone":
        return generate_phone(rng)
    else:
        length = rng.randint(5, 20)
        return "".join(rng.choice(string.ascii_letters + string.digits) for _ in range(length))


def generate_string(constraints: dict[str, Any], rng: random.Random, string_min: int, string_max: int) -> str:
    """Generate a random string within constraints."""
    min_length = constraints.get("minLength", string_min)
    max_length = constraints.get("maxLength", string_max)
    length = rng.randint(min_length, max_length)
    chars = string.ascii_letters + string.digits
    return "".join(rng.choice(chars) for _ in range(length))


def generate_from_pattern(pattern: str, rng: random.Random, string_min: int, string_max: int) -> str:
    """Generate a string matching a regex pattern (basic implementation)."""
    if pattern == r"^\d+$":
        return str(rng.randint(0, 99999))
    elif pattern == r"^[a-zA-Z]+$":
        return "".join(rng.choices(string.ascii_letters, k=10))
    elif pattern == r"^[a-z]+$":
        return "".join(rng.choices(string.ascii_lowercase, k=10))
    elif pattern == r"^[A-Z]+$":
        return "".join(rng.choices(string.ascii_uppercase, k=10))
    else:
        return generate_string({}, rng, string_min, string_max)


def merge_all_of(schemas: list[dict[str, Any]]) -> dict[str, Any]:
    """Merge multiple schemas from allOf."""
    merged: dict[str, Any] = {"type": "object", "properties": {}, "required": []}
    for schema in schemas:
        if "properties" in schema:
            merged["properties"].update(schema["properties"])
        if "required" in schema:
            merged["required"].extend(schema["required"])
        if "type" in schema:
            merged["type"] = schema["type"]
    return merged
