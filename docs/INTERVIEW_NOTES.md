# Interview notes (45 min)

## Walkthrough sugerido (10–12 min)

1. Problema: modernizar PL/pgSQL com qualidade e rastreabilidade.
2. Grafo LangGraph: 4 nós + persistência always-on.
3. Demo live: Anexo D ou E via `POST /modernize`.
4. Mostrar `report` JSON e linha em `modernization_history`.
5. Langfuse / métricas se habilitados.

## Perguntas esperadas

**Por que não mandar a procedure crua no LLM?**  
Porque o PDF exige contexto das etapas anteriores; IR + riscos controlam a tradução e reduzem alucinação.

**Como evita N+1 no Anexo E?**  
Análise marca `cursor_loop` como critical; prompt força set-based/bulk; métrica structural verifica evidências.

**Por que SQL ainda aparece no Python?**  
Preserva semântica/otimizador em CTEs, locks e DML set-based; Python orquestra e valida.

**Como escala?**  
Fila, cache de IR, dialetos plugáveis, swap de modelo por env.

**Limitações honestas?**  
Modelos free, cobertura sintática parcial, equivalência comportamental ainda não automatizada end-to-end.
