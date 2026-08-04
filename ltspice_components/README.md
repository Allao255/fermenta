# Biblioteca de componentes LTspice

Símbolos personalizados para desenhar circuitos compatíveis com o Fermenta (e
com o VIOLA) no LTspice. Copie **todos** estes arquivos para a mesma pasta do
seu `.asc` antes de desenhar. Os símbolos aparecem em `CustomComponents.asc`.

| Arquivo | Componente | Rótulo no netlist |
|---|---|---|
| `IdealOpamp` | amp-op ideal | `OA` |
| `ExtendedSchockleyDiode` | diodo | `D` |
| `ExtendedSchockleyDiodeSeries` | diodos em série | `Dser` |
| `ExtendedSchockleyDiodeAntiParallel` | par antiparalelo (simétrico) | `Dap` |
| `LinearPotentiometer` | potenciômetro linear | `Plin` |
| `LogarithmicPotentiometer` | potenciômetro log | `Plog` |
| `InverseLogarithmicPotentiometer` | potenciômetro log inverso | `Pilog` |

Regras de esquemático e ordem de parâmetros: ver
`docs/GUIA_LTspice_para_nosso_build.md`.

## Origem e licença

Estes arquivos são a biblioteca de componentes do **VIOLA**
(https://github.com/polimi-ispl/viola), redistribuída aqui sob **GPL-3.0** (a
mesma licença do VIOLA e do Fermenta), com crédito aos autores. Ver `CREDITS.md`
na raiz do repositório. Todo o crédito pelos símbolos e pelos modelos de
componente é dos autores do VIOLA (R. Giampiccolo, S. Ravasi, A. Bernardini).
