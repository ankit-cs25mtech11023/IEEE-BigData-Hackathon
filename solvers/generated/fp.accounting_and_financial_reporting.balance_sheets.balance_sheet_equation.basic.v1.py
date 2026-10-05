from fractions import Fraction
import re

def solve(text: str) -> dict:
    # Extract numbers using the provided helper logic (simulated here as per contract)
    # The contract says numbers(text) is already defined, but since I must provide a full solver
    # and the helper isn't actually imported in the execution environment of the model,
    # I will implement a robust extraction based on the problem description.
    # However, the contract says "A helper numbers(text) -> list[Fraction] is already defined".
    # I will assume it exists in the global scope as per the prompt instructions.
    
    # If the helper is not available in the actual runtime, I'll implement a fallback regex
    # to ensure the code works standalone if needed, but strictly following the prompt:
    # "A helper ... is already defined".
    
    try:
        nums = numbers(text)
    except NameError:
        # Fallback implementation if the helper is not injected
        # Pattern: standalone numbers (integers, decimals, fractions) not attached to words
        # This regex looks for numbers that are not immediately preceded or followed by letters
        # but handles cases like "1,200" or "1975/28" or "-3.5"
        pattern = r'(?<![a-zA-Z])(-?\d+(?:,\d{3})*(?:\.\d+)?|-?\d+/\d+)(?![a-zA-Z])'
        matches = re.findall(pattern, text)
        nums = []
        for m in matches:
            m_clean = m.replace(',', '')
            if '/' in m_clean:
                nums.append(Fraction(m_clean))
            else:
                nums.append(Fraction(m_clean))

    # According to the distinct phrasings, the first number is Assets, the second is Liabilities.
    # "A company has total assets of {assets} USD and total liabilities of {liabilities} USD."
    if len(nums) < 2:
        raise ValueError("Not enough numbers found in text.")
    
    assets = nums[0]
    liabilities = nums[1]
    
    # Equation: Assets = Liabilities + Equity
    # Equity = Assets - Liabilities
    equity = assets - liabilities
    
    return {
        "final": equity,
        "steps": {}
    }