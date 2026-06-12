from retrieval import initialize, search

initialize()

results = search("What is Time And Space Complexity?")

print("\nTOP RESULTS:\n")
for r in results:
    print("-", r)