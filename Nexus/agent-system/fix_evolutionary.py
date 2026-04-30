#!/usr/bin/env python3
"""Simple fix - truncate after quick_fitness and add clean ending"""

with open('evolutionary_tools.py', 'r') as f:
    lines = f.readlines()

# Truncate at line 1192 (after return scores in quick_fitness)
truncate = 1192

# Add clean ending
ending = """

# CLI ENTRY POINT
# ============================================

async def main():
    import sys

    if len(sys.argv) < 2:
        print("Usage: python evolutionary_tools.py <intent> [code_file]")
        sys.exit(1)

    intent = sys.argv[1]

    initial_code = {}
    if len(sys.argv) > 2:
        code_path = Path(sys.argv[2])
        if code_path.is_file():
            initial_code = {code_path.name: code_path.read_text()}

    pop = SolutionPopulation(population_size=10, max_generations=20)
    best = await pop.evolve(intent, initial_code)

    print()
    print("="*60)
    print("EVOLUTION COMPLETE")
    print("Best solution: " + best.id)
    print("Fitness: " + str(best.total_fitness))
    print("Scores: " + str(best.fitness))
    print()
    print("Code:")
    for filepath, content in best.code.items():
        print()
        print("--- " + filepath + " ---")
        print(content[:500])
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())
"""

with open('evolutionary_tools.py', 'w') as f:
    f.writelines(lines[:truncate])
    f.write(ending)

print("Fixed - truncated at line 1192")