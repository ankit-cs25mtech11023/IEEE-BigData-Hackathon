from fractions import Fraction
import re

def solve(text: str) -> dict:
    # Extract numbers using regex to find standalone numbers (integers, decimals, fractions)
    # Pattern explanation:
    # (?<![a-zA-Z]) : Negative lookbehind to ensure no letter before
    # -?            : Optional negative sign
    # \d+           : One or more digits
    # (?:\.\d+)?    : Optional decimal part
    # (?:/\d+)?     : Optional fraction part (e.g., 1/2)
    # (?![a-zA-Z])  : Negative lookahead to ensure no letter after
    
    pattern = r'(?<![a-zA-Z])(-?\d+(?:\.\d+)?(?:/\d+)?)(?![a-zA-Z])'
    matches = re.findall(pattern, text)
    
    numbers_list = []
    for m in matches:
        if '/' in m:
            # Fraction
            num, den = m.split('/')
            numbers_list.append(Fraction(int(num), int(den)))
        elif '.' in m:
            # Decimal string to Fraction
            numbers_list.append(Fraction(m))
        else:
            # Integer
            numbers_list.append(Fraction(int(m)))
            
    # Based on the problem structure:
    # 1. Current assets
    # 2. Current liabilities before reclassification
    # 3. Long-term loan total (ignored)
    # 4. Reclassified amount
    
    if len(numbers_list) < 4:
        # Fallback or error handling if extraction fails, though problem guarantees structure
        raise ValueError("Could not extract enough numbers from the text.")

    current_assets = numbers_list[0]
    current_liabilities_initial = numbers_list[1]
    # numbers_list[2] is the total loan, not used
    reclassified_amount = numbers_list[3]
    
    # Step 1: Current ratio before reclassification
    # Ratio = Current Assets / Current Liabilities
    trace_1 = current_assets / current_liabilities_initial
    
    # Step 2: Current liabilities after adding the reclassified amount
    trace_2 = current_liabilities_initial + reclassified_amount
    
    # Step 3: Current ratio after reclassification
    trace_3 = current_assets / trace_2
    
    # Compute the decrease: initial ratio - adjusted ratio
    decrease = trace_1 - trace_3
    
    # The problem asks for the decrease as the final answer.
    # The contract says "the caller applies the required rounding", but the GOLD answers are rounded floats.
    # However, the contract also says "Return exact Fractions/ints for numbers".
    # Since the "final" value is not a slot with a specific rounding spec in the slots list,
    # but the answer_spec defines rounding for the output, we should return the exact value here
    # and let the system handle rounding, OR return the rounded value if the system expects it.
    # Given the error "got None", it implies the function didn't return a dict properly or the keys were missing.
    # I will return the exact Fraction for 'final' as per "Return exact Fractions/ints".
    
    return {
        "final": decrease,
        "steps": {
            "trace_1": trace_1,
            "trace_2": trace_2,
            "trace_3": trace_3
        }
    }