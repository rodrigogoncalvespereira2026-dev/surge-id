(function (root, factory) {
  var api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (root) root.SurgeID = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  var memoryStore = {};

  var store = {
    get: function (key) {
      try {
        if (typeof localStorage !== 'undefined' && localStorage) {
          return localStorage.getItem(key);
        }
      } catch (e) {}
      return Object.prototype.hasOwnProperty.call(memoryStore, key) ? memoryStore[key] : null;
    },
    set: function (key, value) {
      try {
        if (typeof localStorage !== 'undefined' && localStorage) {
          localStorage.setItem(key, value);
          return;
        }
      } catch (e) {}
      memoryStore[key] = value;
    },
    remove: function (key) {
      try {
        if (typeof localStorage !== 'undefined' && localStorage) localStorage.removeItem(key);
      } catch (e) {}
      delete memoryStore[key];
    },
  };

  var listeners = [];

  function callListeners(surge) {
    var status = surge.status();
    listeners.forEach(function (cb) {
      try {
        cb(status);
      } catch (e) {}
    });
  }

  function shallowMerge(base, incoming) {
    var out = {};
    var key;
    if (base) {
      for (key in base) {
        if (Object.prototype.hasOwnProperty.call(base, key)) out[key] = base[key];
      }
    }
    if (incoming) {
      for (key in incoming) {
        if (Object.prototype.hasOwnProperty.call(incoming, key)) out[key] = incoming[key];
      }
    }
    return out;
  }

  var SurgeID = {
    API_BASE: 'https://surge-id.onrender.com',
    TIMEOUT_MS: 8000,
    GAME_SLUG: 'primal_force',
    TOKEN_KEY: 'surgeid_token',
    USER_KEY: 'surgeid_user',

    token: null,
    user: null,
    online: true,
    lastSyncAt: null,
    lastError: null,

    configure: function (options) {
      options = options || {};
      if (options.apiBase) this.API_BASE = String(options.apiBase).replace(/\/+$/, '');
      if (options.gameSlug) this.GAME_SLUG = options.gameSlug;
      if (options.timeoutMs) this.TIMEOUT_MS = Number(options.timeoutMs) || this.TIMEOUT_MS;
      return this;
    },

    restore: function () {
      this.token = store.get(this.TOKEN_KEY);
      var raw = store.get(this.USER_KEY);
      try {
        this.user = raw ? JSON.parse(raw) : null;
      } catch (e) {
        this.user = null;
      }
      if (!this.token) this.user = null;
      return this.status();
    },

    isSignedIn: function () {
      return !!this.token;
    },

    isOnline: function () {
      return this.online;
    },

    status: function () {
      return {
        signedIn: !!this.token,
        online: this.online,
        user: this.user,
        lastSyncAt: this.lastSyncAt,
        lastError: this.lastError,
      };
    },

    on: function (cb) {
      if (typeof cb !== 'function') return function () {};
      listeners.push(cb);
      return function () {
        var i = listeners.indexOf(cb);
        if (i >= 0) listeners.splice(i, 1);
      };
    },

    emit: function () {
      callListeners(this);
    },

    mergeProgress: function (base, incoming) {
      return shallowMerge(base, incoming);
    },

    _setSession: function (data) {
      this.token = data && data.token ? data.token : null;
      this.user = data && data.user ? data.user : null;
      if (this.token) {
        store.set(this.TOKEN_KEY, this.token);
        store.set(this.USER_KEY, JSON.stringify(this.user || null));
        this.lastError = null;
      } else {
        store.remove(this.TOKEN_KEY);
        store.remove(this.USER_KEY);
      }
      this.emit();
    },

    _clearSession: function () {
      this.token = null;
      this.user = null;
      store.remove(this.TOKEN_KEY);
      store.remove(this.USER_KEY);
      this.emit();
    },

    _request: async function (path, options) {
      options = options || {};
      var url = this.API_BASE + path;
      var headers = { 'Content-Type': 'application/json' };
      if (this.token && options.auth !== false) headers.Authorization = 'Bearer ' + this.token;

      var controller = typeof AbortController !== 'undefined' ? new AbortController() : null;
      var timer = null;
      if (controller) {
        var self = this;
        timer = setTimeout(function () {
          controller.abort();
        }, this.TIMEOUT_MS);
      }

      var res;
      try {
        res = await fetch(url, {
          method: options.method || 'GET',
          headers: headers,
          body: options.body ? JSON.stringify(options.body) : undefined,
          signal: controller ? controller.signal : undefined,
        });
      } catch (err) {
        if (timer) clearTimeout(timer);
        this.online = false;
        this.lastError = 'offline';
        this.emit();
        return { ok: false, offline: true, error: 'offline' };
      }
      if (timer) clearTimeout(timer);

      this.online = true;
      var data = null;
      try {
        data = await res.json();
      } catch (e) {
        data = null;
      }

      if (res.status === 401 && options.auth !== false) this._clearSession();

      if (!res.ok) {
        this.lastError = (data && data.error) || 'error';
        this.emit();
        return { ok: false, status: res.status, error: this.lastError, data: data };
      }

      this.lastError = null;
      this.emit();
      return { ok: true, status: res.status, data: data };
    },

    register: async function (payload) {
      payload = payload || {};
      var res = await this._request('/api/auth/register', {
        method: 'POST',
        auth: false,
        body: {
          email: payload.email,
          password: payload.password,
          display_name: payload.displayName,
        },
      });
      if (res.ok && res.data) this._setSession(res.data);
      return res;
    },

    login: async function (payload) {
      payload = payload || {};
      var res = await this._request('/api/auth/login', {
        method: 'POST',
        auth: false,
        body: { email: payload.email, password: payload.password },
      });
      if (res.ok && res.data) this._setSession(res.data);
      return res;
    },

    logout: function () {
      this._clearSession();
      return { ok: true };
    },

    me: async function () {
      var res = await this._request('/api/me');
      if (res.ok && res.data && res.data.user) {
        this.user = res.data.user;
        store.set(this.USER_KEY, JSON.stringify(this.user));
        this.emit();
      }
      return res;
    },

    games: async function () {
      return this._request('/api/games', { auth: false });
    },

    loadProgress: async function (slug) {
      var res = await this._request('/api/me/games/' + (slug || this.GAME_SLUG) + '/progress');
      return res;
    },

    saveProgress: async function (slug, progress) {
      var res = await this._request('/api/me/games/' + (slug || this.GAME_SLUG) + '/progress', {
        method: 'PUT',
        body: { progress: progress || {} },
      });
      return res;
    },

    sync: async function (localProgress, slug) {
      if (!this.isSignedIn()) return { ok: false, reason: 'signed_out' };
      var target = slug || this.GAME_SLUG;
      var push = await this.saveProgress(target, localProgress || {});
      if (!push.ok) return push;
      var pull = await this.loadProgress(target);
      if (!pull.ok) return pull;
      this.lastSyncAt = new Date().toISOString();
      this.emit();
      return {
        ok: true,
        progress: (pull.data && pull.data.progress) || {},
        updated_at: pull.data ? pull.data.updated_at : null,
      };
    },
  };

  SurgeID.restore();
  return SurgeID;
});
