/*
 * Sessão simplificada via localStorage.
 *
 * O backend ainda não emite sessão/JWT (ver README, item pendente
 * "Autenticação de sessão real"). Enquanto isso não existe, o frontend
 * guarda usuario_id/papel localmente após o login, só para saber quem
 * está "logado" na tela — isso NÃO é segurança de verdade, é só estado
 * de UI. As rotas /api/admin/* continuam sem proteção nenhuma no backend.
 */
const SESSAO_KEY = 'pilates_sessao';

function salvarSessao(dados) {
  localStorage.setItem(SESSAO_KEY, JSON.stringify(dados));
}
function obterSessao() {
  const raw = localStorage.getItem(SESSAO_KEY);
  return raw ? JSON.parse(raw) : null;
}
function limparSessao() {
  localStorage.removeItem(SESSAO_KEY);
}
function exigirSessao(papelEsperado) {
  const sessao = obterSessao();
  if (!sessao || (papelEsperado && sessao.papel !== papelEsperado)) {
    window.location.href = '/';
    return null;
  }
  return sessao;
}

async function api(path, options = {}) {
  const sessao = obterSessao();
  const headers = { 'Content-Type': 'application/json' };
  if (sessao && sessao.token) {
    headers['Authorization'] = `Bearer ${sessao.token}`;
  }
  const resp = await fetch(path, {
    headers,
    ...options,
  });
  let data = null;
  try { data = await resp.json(); } catch (e) { /* corpo vazio */ }
  if (!resp.ok) {
    const msg = (data && data.erro) ? data.erro : `Erro ${resp.status}`;
    throw new Error(msg);
  }
  return data;
}

function mostrarAlerta(containerId, mensagem, tipo = 'error') {
  const el = document.getElementById(containerId);
  if (!el) return;
  el.innerHTML = `<div class="alert ${tipo}">${mensagem}</div>`;
}
function limparAlerta(containerId) {
  const el = document.getElementById(containerId);
  if (el) el.innerHTML = '';
}

/*
 * Ícone de mostrar/ocultar senha. Funciona em qualquer campo envolvido em
 * <div class="campo-senha"><input type="password">...<button class="toggle-senha"></button></div>
 * — roda automaticamente em todas as páginas que carregam este script.
 */
const ICONE_OLHO = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>';
const ICONE_OLHO_FECHADO = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17.94 17.94A10.94 10.94 0 0 1 12 20c-7 0-11-8-11-8a18.5 18.5 0 0 1 5.06-5.94M9.9 4.24A10.94 10.94 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19M14.12 14.12a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>';

function inicializarToggleSenha() {
  document.querySelectorAll('.campo-senha').forEach(wrap => {
    const input = wrap.querySelector('input');
    const btn = wrap.querySelector('.toggle-senha');
    if (!input || !btn) return;
    btn.innerHTML = ICONE_OLHO;
    btn.setAttribute('aria-label', 'Mostrar senha');
    btn.addEventListener('click', () => {
      const estaMostrando = input.type === 'text';
      input.type = estaMostrando ? 'password' : 'text';
      btn.innerHTML = estaMostrando ? ICONE_OLHO : ICONE_OLHO_FECHADO;
      btn.setAttribute('aria-label', estaMostrando ? 'Mostrar senha' : 'Ocultar senha');
    });
  });
}
inicializarToggleSenha();

/*
 * Menu hambúrguer mobile — abre/fecha o dropdown de navegação da sidebar
 * em telas estreitas. Roda em qualquer página que tenha #menu-toggle e
 * #sidebar-nav (painel do cliente e painel admin).
 */
function inicializarMenuMobile() {
  const botao = document.getElementById('menu-toggle');
  const nav = document.getElementById('sidebar-nav');
  if (!botao || !nav) return;

  botao.addEventListener('click', () => {
    nav.classList.toggle('aberto');
  });

  // Fecha o menu ao clicar em qualquer link de navegação dentro dele.
  nav.querySelectorAll('a').forEach(link => {
    link.addEventListener('click', () => nav.classList.remove('aberto'));
  });

  // Fecha se clicar fora do menu (fora da sidebar inteira).
  document.addEventListener('click', (e) => {
    if (!nav.classList.contains('aberto')) return;
    if (nav.contains(e.target) || botao.contains(e.target)) return;
    nav.classList.remove('aberto');
  });
}
inicializarMenuMobile();
