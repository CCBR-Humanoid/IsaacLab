import random
from typing import Iterable, Optional

__all__ = ["generate_nickname"]


# Curated, easy-to-spell descriptors (adjectives and present participle verbs)
_DESCRIPTORS: tuple[str, ...] = (
    # adjectives
    "agile", "brave", "bright", "calm", "cheerful", "clever", "cool", "crisp",
    "dapper", "eager", "epic", "fair", "fast", "fierce", "fresh", "friendly",
    "gentle", "giant", "golden", "grand", "happy", "handy", "hardy", "honest",
    "jolly", "joyful", "keen", "kind", "lively", "lucky", "magic", "mellow",
    "merry", "modest", "nifty", "nimble", "noble", "proud", "quick", "quiet",
    "rapid", "ready", "rugged", "sharp", "shiny", "silent", "simple", "slim",
    "smart", "smooth", "snappy", "solid", "speedy", "spry", "steady", "strong",
    "sunny", "super", "swift", "tiny", "tough", "true", "warm", "wise", "zesty",
    # -ing verbs (present participles)
    "blazing", "blooming", "buzzing", "charging", "chirping", "dancing", "dashing",
    "diving", "drifting", "flying", "glowing", "howling", "humming", "jumping",
    "leaping", "racing", "roaming", "rolling", "running", "sailing", "shining",
    "singing", "skipping", "soaring", "sparkling", "sprinting", "surfing",
    "swimming", "trotting", "wandering", "whirling",
)


# One-word animal names, easy to spell
_ANIMALS: tuple[str, ...] = (
    "ant", "bat", "bear", "bee", "bird", "bison", "boar", "buffalo", "camel",
    "cat", "cheetah", "chicken", "cobra", "cougar", "crab", "crane", "crow",
    "deer", "dog", "dolphin", "donkey", "dove", "dragonfly", "duck", "eagle",
    "eel", "elk", "falcon", "ferret", "finch", "fox", "frog", "gazelle",
    "gecko", "goat", "goose", "gopher", "gorilla", "hare", "hawk", "hedgehog",
    "heron", "hippo", "horse", "hound", "hyena", "ibex", "jaguar",
    "jay", "jellyfish", "koala", "koi", "krill", "lemur", "leopard", "lion",
    "lizard", "llama", "lobster", "lynx", "magpie", "mole", "monkey", "moose",
    "mouse", "newt", "octopus", "otter", "owl", "ox", "panda", "panther",
    "parrot", "peacock", "pelican", "penguin", "pig", "pigeon",
    "puma", "quail", "rabbit", "raccoon", "ram", "rat", "raven", "reindeer",
    "rhino", "robin", "salmon", "seal", "shark", "sheep", "shrimp", "skunk",
    "sloth", "snail", "snake", "sparrow", "spider", "squid", "swan", "tiger",
    "toad", "trout", "tuna", "turkey", "turtle", "viper", "vole", "vulture",
    "walrus", "weasel", "whale", "wolf", "wombat", "yak", "zebra",
)


def generate_nickname(
    *,
    rng: Optional[random.Random] = None,
    descriptors: Optional[Iterable[str]] = None,
    animals: Optional[Iterable[str]] = None,
    sep: str = " ",
) -> str:
    """Generate a fun two-word nickname like "jumping rabbit".

    Parameters:
        rng: Optional random number generator to use for selection. Defaults to random.
        descriptors: Optional custom iterable of descriptor words to choose from.
        animals: Optional custom iterable of animal words to choose from.
        sep: Separator between words, defaults to a single space.

    Returns:
        A string in the form "{descriptor}{sep}{animal}".
    """
    r = rng or random
    first_pool = tuple((descriptors or _DESCRIPTORS))
    second_pool = tuple((animals or _ANIMALS))
    if not first_pool or not second_pool:
        raise ValueError("Both descriptors and animals pools must be non-empty.")

    return f"{r.choice(first_pool)}{sep}{r.choice(second_pool)}"
