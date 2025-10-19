import random
import time

MAX_RAND = 99999

def generate_session_id():
    """Randomly generate a session ID of the form {time_ns}-{randint}"""
    return f"{time.time_ns()}-{random.randrange(0, MAX_RAND):05d}"