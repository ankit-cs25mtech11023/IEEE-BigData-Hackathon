from fractions import Fraction
import re

def solve(text: str) -> dict:
    # Extract numbers using the helper logic described (standalone numbers)
    # However, since the prompt says "A helper numbers(text) -> list[Fraction] is already defined",
    # I will implement the extraction logic inline to ensure it works as expected for this specific template.
    # The template has a very specific structure:
    # "pays X USD and issues Y shares valued at Z USD per share."
    # "assets are land A USD, inventory B USD, and patents C USD;"
    # "liabilities are borrowings D USD and accounts payable E USD."
    
    # Let's parse the text to find the specific values based on keywords to be robust against position changes.
    
    # Helper to find a number after a keyword
    def find_val_after(keyword):
        # Look for pattern: keyword followed by optional whitespace, then a number
        # The number might be followed by USD or other text
        pattern = rf"{re.escape(keyword)}\s+(-?\d+(?:,\d+)*(?:\.\d+)?)"
        match = re.search(pattern, text)
        if match:
            return Fraction(match.group(1).replace(',', ''))
        return None

    # 1. Total cash and share consideration (trace_1)
    # "pays [cash] USD and issues [shares] shares valued at [price] USD per share"
    cash = find_val_after(r"pays")
    shares = find_val_after(r"issues")
    price = find_val_after(r"valued at")
    
    if cash is None or shares is None or price is None:
        # Fallback to numbers() if regex fails, but the prompt implies we should use the helper if available.
        # Since I cannot import the helper, I will assume the regex works for the provided templates.
        # If the regex fails, we might need to parse the list of numbers.
        # Let's try a more robust extraction if the specific keywords fail.
        pass

    consideration = cash + (shares * price)
    
    # 2. Total identifiable assets (trace_2)
    # "land [land] USD, inventory [inv] USD, and patents [pat] USD"
    land = find_val_after(r"land")
    inventory = find_val_after(r"inventory")
    patents = find_val_after(r"patents")
    
    total_assets = land + inventory + patents
    
    # 3. Identifiable assets less assumed liabilities (trace_3)
    # "borrowings [borrow] USD and accounts payable [pay] USD"
    borrowings = find_val_after(r"borrowings")
    payables = find_val_after(r"accounts payable")
    
    total_liabilities = borrowings + payables
    net_assets = total_assets - total_liabilities
    
    # Goodwill = consideration - net_assets
    goodwill = consideration - net_assets
    
    return {
        "final": goodwill,
        "steps": {
            "trace_1": consideration,
            "trace_2": total_assets,
            "trace_3": net_assets
        }
    }