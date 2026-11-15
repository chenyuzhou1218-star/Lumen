# Manual de recursos do Lumen

O Lumen é uma equipe de IAs instalada no seu computador Windows. Você só fala com o Lumen, em linguagem comum; ele distribui o trabalho para o membro mais adequado da equipe, escolhe sozinho as ferramentas certas e entrega o resultado para você. Ele escreve código, investiga problemas, edita vídeos, faz modelos 3D, cria páginas da web e PDFs, pesquisa na internet e opera o computador.

## 1. Primeiros passos

- **O que é preciso**: Windows, Python 3.12 e mais um tipo de IA: Claude Code ou Codex (depois de instalado, faça login uma vez no terminal), ou uma chave de API (serviços compatíveis com as interfaces da OpenAI ou da Anthropic também funcionam).
- **Instalação**: na pasta do Lumen, execute `setup.ps1` (as instruções em chinês estão em `安装环境.ps1`). Ele cria uma `.venv` nessa pasta e instala os pacotes de que o Lumen precisa, sem mexer no Python do seu sistema. Depois, dê dois cliques em `Lumen.cmd` para abrir.
- **Primeira abertura**: depois da tela de boas-vindas, escolha o idioma da interface e uma pasta de trabalho, e você já pode começar. O modelo pode ser trocado depois, abaixo da caixa de texto.
- **Aberturas seguintes**: o Lumen volta para a última pasta que você usou. A barra lateral esquerda permite trocar de pasta, abrir um novo chat e pesquisar nos chats.

## 2. Enviando mensagens

- Escreva na caixa de texto o que quer fazer e pressione Enter para enviar. Arquivos podem ser arrastados ou colados ali.
- **Entrada de voz**: clique no microfone e fale. Você pode falar de forma informal; o Lumen entende pelo sentido e não cobra gramática.
- **Modelo**: abaixo da caixa de texto, escolha qual IA usar (Claude Code, Codex ou um modelo do serviço que você conectou); ao lado fica a intensidade de raciocínio. Você decide o modelo por completo; o Lumen nunca troca sozinho.
- **Quando não tem certeza, ele pergunta antes**: se não entender bem o que você quer, aparece um painel de perguntas, com opções prontas em cada uma; basta clicar. Se não quiser responder, pode pular a pergunta e deixar que ele decida.
- **Abaixo da resposta**: copiar, lembrar, responder de novo, ou editar e perguntar outra vez. Quando a resposta termina, as etapas se recolhem e fica só o resultado; clique para ver cada passo.

## 3. Modos de aprovação

Abaixo da caixa de texto, escolha o modo de aprovação desta conversa. Ele define se a IA deve perguntar antes de agir:

| Modo de aprovação | Quando pergunta a você |
|---|---|
| Totalmente liberado | Nunca pergunta; faz direto |
| Revisar para mim | Só pergunta antes de excluir arquivos e antes de usar o mouse ou o teclado no computador |
| Perguntar para mim em tudo | Pergunta antes de cada ação que altere algo |

Quando for preciso perguntar, aparece um pequeno cartão acima da caixa de texto, no canto inferior direito: uma linha descrevendo o que será feito, ao lado de **Permitir** e **Não permitir**. Clicar em **Não permitir** pula só essa ação; as demais continuam normalmente. Fora isso, o Lumen não tem outras restrições de permissão: todas as pastas e todos os discos do computador podem ser usados.

## 4. Equipe Lumen

| Membro | Responsabilidade |
|---|---|
| Lumen | Coordenador: conversa com você, distribui o trabalho e dá a resposta final |
| Spark | Escreve código e também usa várias ferramentas de criação |
| Prism | Inspeciona |
| Torch | Testa na prática: executa o programa de verdade |
| Ray | Pesquisa na internet |
| Lantern | Gerencia arquivos |
| Beacon | Supervisiona: revisa os resultados dos outros |
| Iris | Controla o computador |

Cada membro tem sua própria memória de trabalho e ainda pode chamar assistentes temporários para ajudar. Os membros trabalham ao mesmo tempo sem se sobrepor.

**O Lumen trata você de igual para igual.** Ele fala como um colega competente: se você estiver errado, ele aponta diretamente e explica o motivo; se ele estiver certo, não muda de opinião só porque você insiste, a menos que você apresente um motivo. Quando a decisão for sua, depois que você decidir ele segue exatamente o que foi decidido.

## 5. Uso automático de ferramentas (sem @)

Basta dizer o que quer fazer, por exemplo: "transforme esta imagem em PDF", "corte este vídeo para os primeiros 10 segundos", "crie um cubo 3D vermelho". O Lumen conhece as ferramentas instaladas neste computador, escolhe a adequada e entrega o trabalho ao membro que a tem.

Você também pode digitar @ na caixa de texto para indicar uma ferramenta específica; nesse caso, só essa será usada.

| Ferramenta | Para quê |
|---|---|
| CodeCut | Edição de vídeo: cortes, junções, legendas, trilha sonora, exportação |
| Code3D | Modelos e cenas 3D, usando o Blender instalado no seu computador; exporta GLB e imagens |
| CodeSound | Música e efeitos sonoros |
| CodePage | Páginas da web |
| CodeGame | Pequenos jogos para jogar |
| CodeDeck | Apresentações e documentos (PowerPoint, Word, PDF) |
| CodeData | Análise de Excel e CSV; cada número do relatório tem a origem rastreável |
| CodeCAD | Peças para impressão 3D, com medidas em milímetros |
| CodeLab | Acompanha os registros e o progresso do treinamento de modelos |
| CodeTools | Dezenas de utilitários: pôsteres de logotipo, fluxogramas, QR codes, legendas, dublagem, edição de fotos em lote, organização de arquivos e muito mais |
| CodeFilm | Gera um trecho de vídeo curto a partir de uma frase |
| CodePDF | Imagem para PDF, juntar, dividir, comprimir, girar e selecionar páginas |

## 6. Painel direito

- **Janela de ferramenta**: quando a equipe usa uma ferramenta, ela abre automaticamente à direita, para você acompanhar. Esta janela é de uso exclusivo da IA: ela clica e digita ali sem usar o seu mouse e teclado, e você verá um pequeno cursor azul se movendo. Clique no × da janela para fechá-la.
- **Navegador** (Ctrl+Shift+B): pesquise e abra páginas aqui; os links do chat também abrem aqui. Quando a equipe pesquisa na internet, a navegação também aparece aqui.
- **Terminal** (Ctrl+J): um PowerShell de verdade, na pasta atual. Os comandos executados pela equipe aparecem aqui com cores.

## 7. Memória de longo prazo

- **A IA lembra de você**: antes de cada novo chat começar, a IA revisa as conversas anteriores e resume os pontos principais em uma memória: sobre você (quem você é, como você fala, o que gosta, as regras que estabeleceu; compartilhada por todos os projetos) e sobre este projeto (o que foi feito, o que foi decidido, em que etapa está). O novo chat começa já com essa memória, por isso você não precisa explicar tudo de novo a cada vez.
- **O tamanho depende do histórico**: se você conversou pouco, são algumas linhas; se conversou muito, ela fica maior, normalmente até 50 mil caracteres e no máximo cerca de 80 mil. Acima disso, ela é comprimida de novo, reduzindo só os detalhes sem perder os fatos.
- **Aviso quando precisa esperar**: se a memória da conversa anterior ainda não terminou de ser organizada, o novo chat mostra "Revisando conversas anteriores…" e espera no máximo 90 segundos.
- **Você pode ver, editar e apagar**: em "Configurações → Memória de longo prazo → O que a IA lembra sobre você". O que você alterar passa a ser seguido daqui em diante; ao apagar, as conversas antigas não serão mais usadas para reorganizar a memória.
- Enquanto trabalham, os membros também anotam fatos que vale a pena lembrar e os retomam automaticamente depois; se você escolher um modelo de embedding, eles também conseguem resgatar conclusões antigas escritas com outras palavras, mas com o mesmo sentido.

## 8. Fazendo várias coisas ao mesmo tempo

- Várias conversas podem acontecer ao mesmo tempo sem esperar umas pelas outras: enquanto uma aguarda sua resposta a uma pergunta, a outra continua trabalhando.
- Você pode abrir várias janelas para a mesma pasta (Ctrl+Shift+N).
- O que uma conversa aprende, as outras conversas sabem na próxima vez (veja a seção 7).

## 9. Controle do computador

- Já funciona desde o início: capturas de tela, mouse, teclado, abrir e fechar programas e terminal, em todas as janelas (exceto as do próprio Lumen). Dê o nome do programa ou o caminho completo, e qualquer programa pode ser aberto.
- Se ele vai perguntar antes, depende do modo de aprovação (seção 3).
- **Como opera**: desde o início, trabalha em segundo plano, sem usar o seu mouse e teclado; para jogos e outros casos que exigem o mouse real, mude para primeiro plano em "Configurações → Uso do computador".
- **Parada de emergência**: pressione `Ctrl+Alt+End`, ou leve o mouse ao canto superior esquerdo da tela.
- Se não quiser que a IA mexa no computador: em "Configurações → Uso do computador", ative "Proibir controle do computador".

## 10. Quando precisar de permissão de administrador

Pastas do sistema como `C:\Windows` e `Program Files` exigem permissão de administrador. Quando o Windows mostrar "Acesso negado", a IA executa de novo esse comando como administrador; nesse momento, o próprio Windows mostra a janela de confirmação dele, e cabe a você decidir se permite.

## 11. Testes automáticos

Em "Configurações → Testes automáticos", preencha o comando de testes do projeto (ou clique em "Detectar automaticamente"). Quando a equipe altera código, o sistema roda os testes antes de começar, após cada alteração e antes de entregar (sem passar pelo modelo e sem gastar tokens); quem quebrar um teste que antes passava é apontado na hora. Recomenda-se fazer um commit no git antes de começar, para sempre ver o que mudou e poder desfazer.

## 12. Idioma da interface

English、Français、Español、Deutsch、Italiano、Português、简体中文，一共 7 种，在“设置 → 外观”里切换，马上生效。A janela de ferramentas à direita também muda de idioma. A IA responde no idioma em que você escreve suas mensagens.

## 13. Resumo das configurações

- **Serviços e chaves**: conecte quantos serviços de IA quiser. As chaves ficam apenas no Gerenciador de Credenciais do Windows, nunca em arquivos de configuração.
- **Modelos de IA**: qual serviço e qual modelo cada membro usa, quanto ele deve pensar e qual modelo de reserva usar em caso de erro.
- **Memória de longo prazo**: chave para lembrar, o que a IA lembra sobre você e lembrar por sentido.
- **Testes automáticos** e **Uso do computador**: veja as seções acima.
- **Aparência**: idioma, papel de parede, tamanho da fonte, cor de destaque e outros; as mudanças valem imediatamente.
- **Uso**: quanto foi usado hoje, nos últimos sete dias e no total.
- **Manual de recursos**: é esta página.

## 14. Pequenos recursos úteis

- **Ctrl+K**: uma caixa que encontra tudo: chats, páginas e ações; digite duas ou mais letras e até o que foi dito no chat aparece. **Ctrl+/** mostra todos os atalhos.
- **Ctrl+N** novo chat, **Ctrl+B** recolhe ou mostra a barra lateral esquerda, **Ctrl+F** procura dentro do chat, **Ctrl+,** abre as configurações.
- **Botão direito no chat**: renomear, exportar como Markdown, recolher da lista (sem excluir).
- **Frases prontas**: escreva um trecho e pressione Ctrl+S para salvá-lo como frase pronta; digite / em uma caixa de texto vazia para acioná-la. Um texto ainda não enviado continua guardado mesmo se você fechar a janela.
- **Aviso ao terminar**: quando a janela não está em primeiro plano, a barra de tarefas pisca ao fim da resposta, e um aviso aparece no canto inferior direito.
- **Navegador**: a estrela salva esta página nos favoritos, Ctrl+Shift+T reabre uma aba fechada, e o balão envia esta página para o Lumen.
- **Terminal**: clique com o botão direito na saída e envie ao Lumen a saída selecionada ou a mais recente.

## 15. Segurança e privacidade

- Você escolhe todos os modelos; o Lumen nunca troca sozinho.
- Suas conversas, memórias e registros ficam salvos no seu próprio computador (na pasta `~/.codedoctor`).
- As chaves ficam apenas no Gerenciador de Credenciais do Windows; elas não são guardadas na memória.
- Pagamentos e logins não são feitos pela IA no seu lugar.

## 16. Dicas

- Quanto mais específico você for, mais perto do que quer a primeira resposta vai estar; se não for específico, não tem problema, porque ele vai perguntar antes.
- Para ser mais rápido e gastar menos, escolha um modelo menor ou uma intensidade de raciocínio mais baixa; reserve os modelos maiores para os trabalhos difíceis.
- Se o programa fechar inesperadamente, envie `~/.codedoctor/crash.log` para o desenvolvedor.
