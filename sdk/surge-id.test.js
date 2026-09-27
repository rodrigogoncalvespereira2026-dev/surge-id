const assert = require('node:assert/strict');
const test = require('node:test');

const SurgeID = require('./surge-id.js');

function jsonResponse(status, data) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => data,
  };
}

function useFetch(handler) {
  globalThis.fetch = async (url, options) => handler(url, options || {});
}

function reset() {
  SurgeID.logout();
  SurgeID.configure({ apiBase: 'https://api.test' });
  SurgeID.online = true;
  SurgeID.lastSyncAt = null;
  SurgeID.lastError = null;
}

test('regista conta e guarda sessão', async () => {
  reset();
  useFetch(async (url) => {
    assert.equal(url, 'https://api.test/api/auth/register');
    return jsonResponse(201, {
      token: 'token-1',
      user: { id: 'u1', email: 'a@b.pt', surge_id: 'SG-ABC123' },
    });
  });

  const res = await SurgeID.register({ email: 'a@b.pt', password: 'password123' });
  assert.equal(res.ok, true);
  assert.equal(SurgeID.isSignedIn(), true);
  assert.equal(SurgeID.user.surge_id, 'SG-ABC123');
  assert.equal(SurgeID.restore().signedIn, true);
});

test('login com credenciais erradas não cria sessão', async () => {
  reset();
  useFetch(async () => jsonResponse(401, { error: 'invalid_credentials' }));

  const res = await SurgeID.login({ email: 'a@b.pt', password: 'errada' });
  assert.equal(res.ok, false);
  assert.equal(res.error, 'invalid_credentials');
  assert.equal(SurgeID.isSignedIn(), false);
});

test('401 numa chamada autenticada limpa a sessão', async () => {
  reset();
  SurgeID._setSession({ token: 'velho', user: { id: 'u1' } });
  useFetch(async () => jsonResponse(401, { error: 'invalid_token' }));

  const res = await SurgeID.me();
  assert.equal(res.ok, false);
  assert.equal(SurgeID.isSignedIn(), false);
});

test('sync envia progresso local e devolve o estado da nuvem', async () => {
  reset();
  SurgeID._setSession({ token: 'token-2', user: { id: 'u2' } });

  const calls = [];
  useFetch(async (url, options) => {
    calls.push({ url, method: options.method || 'GET', auth: options.headers.Authorization });
    if (options.method === 'PUT') {
      return jsonResponse(200, { game: 'primal_force', progress: { moedas: 99, nivel: 3 } });
    }
    return jsonResponse(200, {
      game: 'primal_force',
      progress: { moedas: 99, nivel: 3, trofeus: 12 },
    });
  });

  const res = await SurgeID.sync({ moedas: 99, nivel: 3 });
  assert.equal(res.ok, true);
  assert.deepEqual(res.progress, { moedas: 99, nivel: 3, trofeus: 12 });
  assert.equal(calls.length, 2);
  assert.equal(calls[0].method, 'PUT');
  assert.equal(calls[0].auth, 'Bearer token-2');
  assert.ok(SurgeID.lastSyncAt);
});

test('sync sem sessão devolve signed_out', async () => {
  reset();
  const res = await SurgeID.sync({ moedas: 1 });
  assert.equal(res.ok, false);
  assert.equal(res.reason, 'signed_out');
});

test('falha de rede marca offline e não lança erro', async () => {
  reset();
  SurgeID._setSession({ token: 'token-3', user: { id: 'u3' } });
  const statusEvents = [];
  const off = SurgeID.on((status) => statusEvents.push(status.online));

  globalThis.fetch = async () => {
    throw new Error('network down');
  };

  const res = await SurgeID.sync({ moedas: 5 });
  assert.equal(res.ok, false);
  assert.equal(res.offline, true);
  assert.equal(SurgeID.isOnline(), false);
  assert.ok(statusEvents.includes(false));
  assert.equal(SurgeID.isSignedIn(), true);
  off();
});

test('mergeProgress faz merge raso com prioridade para o segundo', () => {
  const merged = SurgeID.mergeProgress({ moedas: 1, nivel: 2 }, { moedas: 7 });
  assert.deepEqual(merged, { moedas: 7, nivel: 2 });
});
