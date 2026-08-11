/*
 * Chatbot público — fluxo guiado por botões/formulários, sem IA.
 *
 * Importante: este widget NUNCA anexa exame nem grava dado sensível
 * direto no prontuário de um cliente existente, mesmo que a pessoa
 * informe um e-mail que já é de um cadastro real. Sem senha, não dá pra
 * confirmar quem está do outro lado da conversa — deixar escrever direto
 * no prontuário seria uma falha de segurança. Em vez disso, tudo vira uma
 * "solicitação" (chatbot_solicitacoes) que um admin revisa manualmente.
 */
(function () {
  const FRASES = {
    inicio: 'Olá! Sou o assistente virtual da clínica. Como posso ajudar?',
    pedirEmail: 'Qual é o seu e-mail?',
    encontrado: (nome) => `Olá, ${nome}! Encontrei seu cadastro.`,
    naoEncontrado: 'Não encontrei esse e-mail no nosso cadastro. Qual é o seu nome completo?',
    pedirTelefone: 'Qual o seu telefone/WhatsApp para retorno?',
    pedirComorbidade: 'Quer nos contar sobre alguma comorbidade? (opcional)',
    pedirPreferencias: 'Tem preferência de sala, profissional, data ou horário? (opcional)',
    pedirMensagem: 'Quer deixar mais alguma informação? (opcional)',
    final: 'Recebemos sua solicitação! A clínica vai entrar em contato pelo telefone ou e-mail em breve.',
    avisoExame: 'Para enviar exames com segurança, é necessário fazer login na sua conta.',
  };

  const estado = {
    tipo_atendimento: null,
    email: null,
    nome: null,
    ja_cadastrado: false,
    telefone: null,
    comorbidade: null,
    sala_desejada: null,
    profissional_desejado: null,
    data_desejada: null,
    horario_desejado: null,
    mensagem: null,
  };

  function montarWidget() {
    const fab = document.createElement('button');
    fab.id = 'chatbot-fab';
    fab.className = 'chatbot-fab';
    fab.setAttribute('aria-label', 'Falar com a clínica');
    fab.textContent = '💬';
    document.body.appendChild(fab);

    const painel = document.createElement('div');
    painel.id = 'chatbot-painel';
    painel.className = 'chatbot-painel';
    painel.style.display = 'none';
    painel.innerHTML = `
      <div class="chatbot-header">
        <span>Fale com a clínica</span>
        <button type="button" id="chatbot-fechar" aria-label="Fechar">✕</button>
      </div>
      <div class="chatbot-mensagens" id="chatbot-mensagens"></div>
      <div class="chatbot-area-input" id="chatbot-area-input"></div>
    `;
    document.body.appendChild(painel);

    fab.addEventListener('click', () => {
      const abrindo = painel.style.display === 'none';
      painel.style.display = abrindo ? 'flex' : 'none';
      if (abrindo && document.getElementById('chatbot-mensagens').children.length === 0) {
        iniciarConversa();
      }
    });
    document.getElementById('chatbot-fechar').addEventListener('click', () => {
      painel.style.display = 'none';
    });
  }

  function mensagemBot(texto) {
    const container = document.getElementById('chatbot-mensagens');
    const bolha = document.createElement('div');
    bolha.className = 'chatbot-msg bot';
    bolha.textContent = texto;
    container.appendChild(bolha);
    container.scrollTop = container.scrollHeight;
  }

  function mensagemUsuario(texto) {
    const container = document.getElementById('chatbot-mensagens');
    const bolha = document.createElement('div');
    bolha.className = 'chatbot-msg user';
    bolha.textContent = texto;
    container.appendChild(bolha);
    container.scrollTop = container.scrollHeight;
  }

  function areaInput(html) {
    document.getElementById('chatbot-area-input').innerHTML = html;
  }

  function iniciarConversa() {
    mensagemBot(FRASES.inicio);
    areaInput(`
      <div class="chatbot-opcoes">
        <button type="button" class="chatbot-opcao" data-tipo="pilates">Agendar Pilates</button>
        <button type="button" class="chatbot-opcao" data-tipo="fisioterapia">Consulta de Fisioterapia</button>
        <button type="button" class="chatbot-opcao" data-tipo="outro">Outro assunto</button>
      </div>
    `);
    document.querySelectorAll('.chatbot-opcao').forEach(btn => {
      btn.addEventListener('click', () => {
        estado.tipo_atendimento = btn.dataset.tipo;
        mensagemUsuario(btn.textContent);
        passoEmail();
      });
    });
  }

  function passoEmail() {
    mensagemBot(FRASES.pedirEmail);
    areaInput(`
      <input type="email" id="chatbot-input-email" placeholder="seu@email.com">
      <button type="button" id="chatbot-btn-email">Enviar</button>
    `);
    document.getElementById('chatbot-btn-email').addEventListener('click', async () => {
      const email = document.getElementById('chatbot-input-email').value.trim();
      if (!email) return;
      estado.email = email;
      mensagemUsuario(email);
      areaInput('<p class="chatbot-carregando">Verificando...</p>');
      try {
        const resp = await fetch('/api/chatbot/verificar-email', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email }),
        });
        const data = await resp.json();
        if (data.existe) {
          estado.nome = data.nome;
          estado.ja_cadastrado = true;
          mensagemBot(FRASES.encontrado(data.nome));
          passoTelefone();
        } else {
          passoNome();
        }
      } catch (e) {
        mensagemBot('Tive um problema para verificar seu e-mail. Vamos continuar mesmo assim.');
        passoNome();
      }
    });
  }

  function passoNome() {
    mensagemBot(FRASES.naoEncontrado);
    areaInput(`
      <input type="text" id="chatbot-input-nome" placeholder="Nome completo">
      <button type="button" id="chatbot-btn-nome">Enviar</button>
    `);
    document.getElementById('chatbot-btn-nome').addEventListener('click', () => {
      const nome = document.getElementById('chatbot-input-nome').value.trim();
      if (!nome) return;
      estado.nome = nome;
      mensagemUsuario(nome);
      passoTelefone();
    });
  }

  function passoTelefone() {
    mensagemBot(FRASES.pedirTelefone);
    areaInput(`
      <input type="text" id="chatbot-input-telefone" placeholder="(83) 99999-9999">
      <button type="button" id="chatbot-btn-telefone">Enviar</button>
    `);
    document.getElementById('chatbot-btn-telefone').addEventListener('click', () => {
      const telefone = document.getElementById('chatbot-input-telefone').value.trim();
      estado.telefone = telefone || null;
      mensagemUsuario(telefone || '(não informado)');
      passoComorbidade();
    });
  }

  function passoComorbidade() {
    mensagemBot(FRASES.pedirComorbidade);
    areaInput(`
      <textarea id="chatbot-input-comorbidade" rows="2" placeholder="Opcional"></textarea>
      <div style="display:flex; gap:0.5em;">
        <button type="button" id="chatbot-btn-comorbidade">Continuar</button>
        <button type="button" class="chatbot-secundario" id="chatbot-btn-pular-comorbidade">Pular</button>
      </div>
    `);
    const seguir = () => {
      const texto = document.getElementById('chatbot-input-comorbidade').value.trim();
      estado.comorbidade = texto || null;
      mensagemUsuario(texto || '(pulou)');
      if (estado.tipo_atendimento === 'outro') {
        passoMensagem();
      } else {
        passoPreferencias();
      }
    };
    document.getElementById('chatbot-btn-comorbidade').addEventListener('click', seguir);
    document.getElementById('chatbot-btn-pular-comorbidade').addEventListener('click', seguir);
  }

  async function passoPreferencias() {
    mensagemBot(FRASES.pedirPreferencias);
    areaInput('<p class="chatbot-carregando">Carregando opções...</p>');
    try {
      const resp = await fetch('/api/agendamentos/opcoes');
      const opcoes = await resp.json();
      areaInput(`
        <select id="chatbot-sala">
          <option value="">Sala (qualquer uma)</option>
          ${opcoes.salas.map(s => `<option value="${s.nome}">${s.nome}</option>`).join('')}
        </select>
        <select id="chatbot-profissional">
          <option value="">Profissional (qualquer um)</option>
          ${opcoes.profissionais.map(p => `<option value="${p.nome}">${p.nome}</option>`).join('')}
        </select>
        <input type="date" id="chatbot-data">
        <input type="time" id="chatbot-horario">
        <div style="display:flex; gap:0.5em;">
          <button type="button" id="chatbot-btn-preferencias">Continuar</button>
          <button type="button" class="chatbot-secundario" id="chatbot-btn-pular-preferencias">Pular</button>
        </div>
      `);
    } catch (e) {
      areaInput(`<div style="display:flex; gap:0.5em;">
        <button type="button" class="chatbot-secundario" id="chatbot-btn-pular-preferencias">Continuar</button>
      </div>`);
    }

    const seguir = () => {
      const sala = document.getElementById('chatbot-sala');
      const prof = document.getElementById('chatbot-profissional');
      const data = document.getElementById('chatbot-data');
      const horario = document.getElementById('chatbot-horario');
      estado.sala_desejada = sala ? sala.value || null : null;
      estado.profissional_desejado = prof ? prof.value || null : null;
      estado.data_desejada = data ? data.value || null : null;
      estado.horario_desejado = horario ? horario.value || null : null;
      mensagemUsuario('Preferências registradas.');
      passoMensagem();
    };
    const btnPrincipal = document.getElementById('chatbot-btn-preferencias');
    if (btnPrincipal) btnPrincipal.addEventListener('click', seguir);
    document.getElementById('chatbot-btn-pular-preferencias').addEventListener('click', seguir);
  }

  function passoMensagem() {
    mensagemBot(FRASES.pedirMensagem);
    areaInput(`
      <textarea id="chatbot-input-mensagem" rows="2" placeholder="Opcional"></textarea>
      <div style="display:flex; gap:0.5em;">
        <button type="button" id="chatbot-btn-mensagem">Enviar solicitação</button>
        <button type="button" class="chatbot-secundario" id="chatbot-btn-pular-mensagem">Pular e enviar</button>
      </div>
    `);
    const enviar = async () => {
      const texto = document.getElementById('chatbot-input-mensagem').value.trim();
      estado.mensagem = texto || null;
      mensagemUsuario(texto || '(pulou)');
      areaInput('<p class="chatbot-carregando">Enviando...</p>');
      try {
        await fetch('/api/chatbot/solicitacao', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(estado),
        });
        mensagemBot(FRASES.final);
        if (estado.tipo_atendimento !== 'outro') {
          mensagemBot(FRASES.avisoExame);
        }
        areaInput(`
          <div style="display:flex; gap:0.5em;">
            <a href="/" class="btn" style="text-decoration:none; text-align:center;">Fazer login</a>
            <button type="button" class="chatbot-secundario" id="chatbot-btn-nova">Nova solicitação</button>
          </div>
        `);
        document.getElementById('chatbot-btn-nova').addEventListener('click', () => {
          document.getElementById('chatbot-mensagens').innerHTML = '';
          Object.keys(estado).forEach(k => estado[k] = null);
          estado.ja_cadastrado = false;
          iniciarConversa();
        });
      } catch (e) {
        mensagemBot('Não consegui enviar agora. Tente novamente em instantes.');
      }
    };
    document.getElementById('chatbot-btn-mensagem').addEventListener('click', enviar);
    document.getElementById('chatbot-btn-pular-mensagem').addEventListener('click', enviar);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', montarWidget);
  } else {
    montarWidget();
  }
})();
