# Créditos e licença

## VIOLA (obra original)

Este projeto reimplementa e se integra ao método do **VIOLA**:

> R. Giampiccolo, S. Ravasi, and A. Bernardini, *"VIOLA: A Framework for the
> Automatic Generation of Virtual Analog Audio Plug-ins based on WDFs"*,
> Journal of the Audio Engineering Society (special issue "The Sound of Digital
> Audio Effects").

Repositório oficial: https://github.com/polimi-ispl/viola — licenciado sob
**GPL-3.0**. Todo o crédito pelo método (WDF topológico tipo-R, tapers de
potenciômetro, solver de diodo, deploy via MATLAB Audio Toolbox/Coder) é dos
autores do VIOLA.

Este repositório redistribui **apenas** a biblioteca de componentes LTspice do
VIOLA (os símbolos `.asy/.asc` em `ltspice_components/`), sob GPL-3.0 e com
crédito — por serem pequenos e essenciais para desenhar circuitos. O **framework
MATLAB** (parser, geração de plugin, exemplos, binários e medições) **não** é
redistribuído; obtenha-o do repositório oficial e use os arquivos de
`viola_integration/` por cima do clone.

## Este projeto (fermenta)

`fermenta` é uma reimplementação independente, em Python, do **método** do VIOLA,
mais um gerador próprio de código C++/JUCE, uma GUI e ferramentas de comparação.
O núcleo Python foi escrito do zero para espelhar o pipeline do VIOLA, de modo a
permitir comparação um-a-um.

## Licença deste projeto

Dada a proximidade com o VIOLA (GPL-3.0), a escolha conservadora e recomendada
é licenciar este projeto também sob **GPL-3.0**, mantendo os créditos acima.

> Observação: isto é uma recomendação prática, não aconselhamento jurídico. A
> decisão final de licença é sua; se optar por GPL-3.0, o GitHub adiciona o
> texto canônico da licença ao criar o repositório (ver `PUBLISH.md`).

## Dependências de terceiros usadas

- **JUCE** (geração do VST3) — licença própria do JUCE (dual: GPL/commercial),
  baixada via CMake FetchContent no momento da compilação; não redistribuída
  aqui.
- **NumPy**, **Matplotlib** — BSD.
