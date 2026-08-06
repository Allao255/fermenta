# Fermenta

*[English version](README.md)*

**De um circuito no LTspice a um plugin de pedal de guitarra (VST3), via Wave
Digital Filters.** O Fermenta é um port de código aberto, em Python, do método
por trás do [VIOLA](https://github.com/polimi-ispl/viola), com gerador de código
C++/JUCE, interface gráfica e ferramentas de comparação próprios — dispensando
MATLAB e toolboxes pagas para construir um pedal.

Desenhe o circuito no LTspice, exporte o netlist SPICE, carregue no aplicativo,
escolha o nó de saída, nomeie os knobs e gere o plugin.

---

## O que faz

A partir de um netlist LTspice, o Fermenta:

1. faz o parsing e monta o grafo do circuito;
2. forma a matriz fundamental de corte `Q`, a de laço `B` e a matriz de
   espalhamento `S` do tipo-R — uma única junção para o circuito inteiro,
   derivada da topologia;
3. roda o laço de ondas por amostra (redes lineares, diodos em forma fechada
   pela função Wright omega, amp-ops ideais como nullors e múltiplas não
   linearidades pela iteração SIM/DSR);
4. emite um motor de DSP autossuficiente em C++;
5. embrulha em JUCE e compila um VST3.

### Classes de circuito suportadas

| Classe | Exemplo | Método |
|---|---|---|
| `lin` | rede RC | espalhamento tipo-R |
| `one_non_lin` | clipper de diodo | Wright omega, forma fechada |
| `lin_opamp` | equalizador gráfico | nullor (grafo dual) |
| `one_non_lin_opamp` | Tube Screamer, MXR Distortion+ | nullor + diodo |
| `non_lin[_opamp]` | DOD 250 | iteração SIM/DSR |

Componentes: resistores, capacitores, indutores, fontes de tensão/corrente,
diodos de Shockley estendido (simples, em série, antiparalelos), potenciômetros
lineares/log/log-inverso e amp-ops ideais. Transistores não são modelados.

---

## Primeiros passos (Windows, do zero)

1. Baixe ou clone este repositório.
2. Clique com o botão direito em `setup_windows.bat` → **Executar como
   administrador**. Ele instala Git, Python, CMake e o Visual Studio 2022 Build
   Tools via `winget`.
3. Feche a janela e dê dois cliques em `abrir_app.bat` — ele instala as
   dependências Python e abre o aplicativo.

No app: **Load** no netlist → **Analyze** → escolha o nó de saída → defina um
nome e os rótulos dos knobs → **Export & Build VST3**. O plugin aparece em
`<pasta>\build\<Nome>_artefacts\Release\VST3\`.

### Pela linha de comando

```bash
cd python
pip install -e ".[gui]"
pytest                       # suíte de testes

python -m fermenta.gui       # aplicativo principal
python -m fermenta.compare   # compara dois pedais (tempo, espectro, métricas)
```

Compilar um VST3 exige CMake e um compilador C++; o JUCE é baixado
automaticamente na primeira compilação.

---

## Desenhando o circuito

Copie os símbolos de `ltspice_components/` para a pasta do seu arquivo `.asc` e
siga as convenções de esquemático do VIOLA: exatamente uma fonte de entrada
chamada `Vin`, terra como nó `0`, IDs de componente únicos, rótulos de nó
inalterados (`N001`, `N002`, …) e peças customizadas nomeadas `OA1`, `D1`,
`Dser1`, `Dap1`, `Plin1`/`Plog1`/`Pilog1` — potenciômetros numerados em
sequência, já que essa ordem é a ordem dos knobs.

Exporte com **View → SPICE Netlist** (e não *Tools → Export Netlist*, que gera
um netlist de PCB).

Como o amp-op é ideal, as trilhas de alimentação não são modeladas: onde o
esquemático mostra uma polarização de meia-tensão (por exemplo +4,5 V), conecte
ao nó `0`.

Os guias completos, incluindo o caminho por MATLAB/VIOLA, estão em `docs/`.

---

## Validação

O Fermenta é um port, então a referência é o próprio VIOLA. São três verificações
independentes:

- **Contra um oráculo MNA.** Cada classe de circuito é comparada a um solver
  nodal independente (Newton para diodos, stamps de nullor para amp-ops):
  `pytest`, 19 testes.
- **Contra os plugins gerados pelo próprio VIOLA.** RC 302 dB, DEMO 220 dB, DOD
  na precisão de máquina e um estágio de clipping de Tube Screamer a ~287 dB de
  SNR.
- **Verificação cruzada aleatorizada.** O `tools/fuzz_vs_viola.py` gera circuitos
  aleatórios (todas as classes, diodos em qualquer posição da topologia,
  múltiplos amp-ops, indutores, potenciômetros) e compara a engine com o
  `tools/viola_reference.py`, uma segunda implementação transcrita das fontes
  MATLAB que calcula a matriz de espalhamento por outro caminho. Nenhuma
  divergência estrutural em 320 circuitos.

O C++ gerado é idêntico bit a bit à engine Python nos circuitos lineares e fica
dentro do ruído numérico nos não lineares mal condicionados
(`tools/validate_cpp.py`).

### Reproduzindo as verificações

Tudo abaixo roda a partir de um clone, sem MATLAB e sem instalar o VIOLA (os
netlists de exemplo acompanham o repositório em `examples/viola/`):

```bash
cd python
pip install -e .
pytest                              # 19 testes contra um oráculo MNA independente
python tools/validate_cpp.py        # C++ gerado vs a engine Python
python tools/fuzz_vs_viola.py 0 100 # 100 circuitos aleatórios vs a segunda implementação
python example_demo.py              # menor execução de ponta a ponta
```

Reproduzir a comparação contra os plugins do *próprio* VIOLA exige, além disso,
MATLAB com Audio Toolbox e MATLAB Coder; ver `viola_integration/`.

Vale registrar uma decisão de projeto: o VIOLA calcula a resistência de porta
adaptada do diodo por uma redução nullor-MNA cuja indexação se afasta da
resistência de Thévenin física quando o diodo está dentro da malha de
realimentação de um amp-op. O Fermenta reproduz a formulação do VIOLA de
propósito, para que os plugins coincidam com os que o VIOLA gera. Ver
`docs/PROJECT_OVERVIEW.md`, seção 7.

---

## Estrutura do repositório

```
python/       biblioteca (fermenta/), CLI e ferramentas de validação, testes
cpp/          templates C++/JUCE do plugin
examples/     netlists de exemplo
ltspice_components/   símbolos LTspice para desenhar circuitos
viola_integration/    arquivos para usar num clone do VIOLA (caminho MATLAB)
docs/         guias, panorama do projeto, notas teóricas
```

---

## Créditos e licença

O Fermenta reimplementa o método publicado em:

> R. Giampiccolo, S. Ravasi e A. Bernardini, *"VIOLA: A Framework for the
> Automatic Generation of Virtual Analog Audio Plug-ins based on WDFs"*, Journal
> of the Audio Engineering Society, edição especial "The Sound of Digital Audio
> Effects".

Todo o crédito pelo método é de seus autores. A biblioteca de símbolos LTspice
em `ltspice_components/` vem do repositório do VIOLA e é redistribuída aqui sob
a GPL-3.0; o framework MATLAB em si não é redistribuído. Ver `CREDITS.md`.

Licenciado sob **GPL-3.0**, como o VIOLA.

### Nota de desenvolvimento

Este projeto foi desenvolvido com o auxílio de um modelo de linguagem de grande
porte (Claude, da Anthropic), usado na implementação do código, no port dos
algoritmos em MATLAB e na construção das ferramentas de validação. Todos os
resultados relatados aqui são reprodutíveis com os scripts em `python/tools/`, e
a engine é verificada contra os plugins gerados pelo próprio VIOLA e contra uma
implementação independente.
