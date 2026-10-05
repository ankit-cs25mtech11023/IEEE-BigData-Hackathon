from fractions import Fraction
import re

def solve(text: str) -> dict:
    nums = numbers(text)
    cash = nums[0]
    payables = nums[1]
    result = cash - payables
    return {"final": result, "steps": {}}