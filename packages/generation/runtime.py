
from functools import lru_cache

from packages.generation.answer_generator import AnswerGenerator


@lru_cache(maxsize=1)
def get_answer_generator() -> AnswerGenerator:
    return AnswerGenerator()


def clear_generation_cache():
    get_answer_generator.cache_clear()
