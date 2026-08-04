# Fermenta

**Reimplementação em Python do método do [VIOLA](https://github.com/polimi-ispl/viola)**
para transformar circuitos de pedais de guitarra (desenhados no LTspice) em
plugins de áudio (VST3) via **Wave Digital Filters (WDF)** com espalhamento
topológico do tipo-R — com um gerador de código C++/JUCE, uma interface gráfica
e ferramentas de comparação próprios.

> Este projeto reimplementa o **método** do VIOLA e o credita integralmente.
> Não redistribui o código do VIOLA. Ver `CREDITS.md`.

---

## O que ele faz

Dado um netlist LTspice de um pedal, o `fermenta`:

1. **Parseia** o netlist e monta o grafo do circuito.
2. Constrói as **matrizes fundamentais** de corte `Q` e de laço `B` e a matriz
   de **espalhamento** `S` — uma única junção WDF a partir da topologia.
3. Roda o **laço de onda por amostra** (linear, diodos em forma fechada,
   amp-ops como nullor, e múltiplas não linearidades via solver iterativo).
4. **Gera C++** — um motor de DSP autossuficiente por circuito.
5. **Empacota num VST3** com um wrapper JUCE.

Tudo isso acessível por uma **GUI** (carregar netlist → analisar → mover knobs →
ver gráficos → exportar/compilar o plugin) e comparável ao VIOLA por uma
ferramenta de **comparação** (tempo/frequência + métricas).

## Classes de circuito suportadas

| Classe | Exemplo | Método |
|---|---|---|
| `lin` | RC | espalhamento tipo-R |
| `one_non_lin` | diode clipper | diodo Wright-omega (forma fechada) |
| `lin_opamp` | equalizador | nullor (grafo dual) |
| `one_non_lin_opamp` | Tube Screamer, MXR | nullor + diodo |
| `non_lin[_opamp]` | DOD 250 | solver iterativo SIM/DSR |

## Validação

- Suíte `pytest` (19 testes) contra um oráculo nodal/MNA independente
  (núcleo linear a ~1e-14).
- Comparação bit-a-bit contra o plugin gerado pelo próprio VIOLA:
  RC **302 dB**, DEMO **220 dB**, MXR **87.5 dB**, DOD **precisão de máquina**.
- C++ gerado idêntico à engine Python (~1e-15).

Detalhes e achados de fidelidade em `docs/PROJECT_OVERVIEW.md`.

---

## Começando

```bash
cd python
pip install -e ".[gui]"      # instala a lib + matplotlib
pytest                        # roda os testes

python -m fermenta.gui        # abre a interface (ou run_gui.bat)
python -m fermenta.compare    # abre o comparador de pedais
```

Para compilar um VST3 é preciso **CMake** + **Visual Studio 2022** (Desktop C++).
A primeira compilação baixa o JUCE.

## Documentação

A documentação detalhada (panorama do projeto, guias LTspice→VST3 e a teoria
WDF) está sendo preparada e será adicionada em breve. Enquanto isso:

- `viola_integration/` — arquivos para integrar com um clone do VIOLA.
- `ltspice_components/` — símbolos LTspice para desenhar os circuitos.

## Estrutura

```
python/      biblioteca (fermenta/), CLI (tools/), testes (tests/)
cpp/         templates C++/JUCE do plugin
examples/    netlists de exemplo
ltspice_components/ símbolos LTspice p/ desenhar circuitos (do VIOLA, GPL-3.0)
viola_integration/  nossos arquivos p/ o clone do VIOLA (não incluído)
```

## Licença

Recomendada **GPL-3.0** (alinhada ao VIOLA). Ver `CREDITS.md`.
