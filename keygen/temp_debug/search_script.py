
import sys

def search_in_file(filename, terms):
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            content = f.read()
            
        print(f"File size: {len(content)} chars")
        
        for term in terms:
            print(f"\n--- Searching for '{term}' ---")
            start = 0
            count = 0
            while True:
                idx = content.find(term, start)
                if idx == -1:
                    break
                
                # Context window
                s = max(0, idx - 100)
                e = min(len(content), idx + 500)
                print(f"Match {count+1} at {idx}:")
                print(content[s:e])
                print("-" * 40)
                
                start = idx + 1
                count += 1
                if count >= 3: # Limit to 3 matches per term
                    break
            
            if count == 0:
                print("Not found.")

    except Exception as e:
        print(f"Error: {e}")

search_in_file('temp_debug/index-DdrK3shG.js', ['capsule', 'heart', 'Outline', 'outline', 'ExtrudeGeometry'])
