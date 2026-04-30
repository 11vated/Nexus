"""Multi-Agent Cognitive Evolution System.

An evolutionary framework where agent populations:
- Compete on coding tasks
- Breed successful strategies
- Mutate configurations
- Transfer knowledge across agents
- Continuously improve over generations

Inspired by genetic algorithms and population-based training.
"""

from nexus.evolution.evolution_engine import EvolutionEngine, EvolutionConfig
from nexus.evolution.agent_population import AgentPopulation, AgentGenome
from nexus.evolution.cognitive_fitness import CognitiveFitness, FitnessMetrics
from nexus.evolution.strategy_crossover import StrategyCrossover
from nexus.evolution.mutation import MutationEngine
from nexus.evolution.knowledge_transfer import KnowledgeTransfer

__all__ = [
    "EvolutionEngine",
    "EvolutionConfig",
    "AgentPopulation",
    "AgentGenome",
    "CognitiveFitness",
    "FitnessMetrics",
    "StrategyCrossover",
    "MutationEngine",
    "KnowledgeTransfer",
]
