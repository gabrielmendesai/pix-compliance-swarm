"""Agentes Pydantic AI do enxame (SPEC-008 e além).

Cada módulo deste pacote corresponde a um agente do enxame, com uma única
responsabilidade (Princípio IV da constituição). `scraper_agent.py` é o
primeiro — estabelece o padrão estrutural (`deps_type`, `RunContext`,
`output_type`, tratamento de erro de dependência externa) reutilizado pelos
seis agentes seguintes.
"""
