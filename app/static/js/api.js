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
