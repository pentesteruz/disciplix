// For monorepo setup, we use relative paths as the frontend is served by the same backend
export const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

function debugEnabled() {
  if (typeof window === "undefined") return false;
  return new URLSearchParams(window.location.search).get("debug") === "1";
}

function logDebug(...args: any[]) {
  if (debugEnabled()) {
    // eslint-disable-next-line no-console
    console.log("[WEBAPP DEBUG]", ...args);
  }
}

// A custom fetch wrapper that automatically attaches the Telegram initData
export async function tgFetch(url: string, options: RequestInit = {}) {
  let initData = "";
  if (typeof window !== "undefined" && (window as any).Telegram?.WebApp?.initData) {
    initData = (window as any).Telegram.WebApp.initData;
  }

  const headers = new Headers(options.headers || {});
  if (initData) {
    headers.set("Authorization", initData);
  }

  logDebug("API_BASE", API_BASE);
  logDebug("Request", url, options);
  logDebug("Auth header", headers.get("Authorization") ? "set" : "missing");
  
  // Set Content-Type by default if not set for JSON bodies
  if (options.body && typeof options.body === 'string' && !headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
  }

  const config: RequestInit = {
    ...options,
    headers,
  };

  const fullUrl = `${API_BASE}${url}`;
  const response = await fetch(fullUrl, config);
  logDebug("Response", fullUrl, response.status);
  
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    logDebug("Error payload", errorData);
    throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
  }
  
  return response.json();
}

// User Data
export async function getUserData(userId: string | number) {
  return tgFetch(`/api/user_data/${userId}`);
}

export async function getDashboardStats(userId: string | number) {
  return tgFetch(`/api/dashboard?user_id=${userId}`);
}

export async function getProfileStats(userId: string | number) {
  return tgFetch(`/api/profile/${userId}`);
}

export async function getFinance(userId: string | number) {
  return tgFetch(`/api/finance/${userId}`);
}

// Tasks
export async function addTask(userId: string | number, title: string, description: string, dueDate: string) {
  return tgFetch(`/api/tasks/${userId}`, {
    method: "POST",
    body: JSON.stringify({ title, description, due_date: dueDate }),
  });
}

export async function completeTask(taskId: string | number) {
  return tgFetch(`/api/tasks/complete/${taskId}`, { method: "POST" });
}

// Dreams
export async function createDream(userId: string | number, name: string, amount: number, deadline: string, daily_limit: number, icon: string, iconBg: string, iconColor: string) {
  return tgFetch(`/api/dreams/${userId}`, {
    method: "POST",
    body: JSON.stringify({ name, amount, deadline, daily_limit, icon, iconBg, iconColor }),
  });
}

export async function addDreamProgress(dreamId: string | number, amount: number, isDaily: boolean = false) {
  return tgFetch(`/api/dreams/${dreamId}/progress`, {
    method: "POST",
    body: JSON.stringify({ amount, is_daily: isDaily }),
  });
}

export async function requestCancelDream(dreamId: string | number) {
  return tgFetch(`/api/dreams/${dreamId}/cancel_request`, { method: "POST" });
}

export async function undoCancelDream(dreamId: string | number) {
  return tgFetch(`/api/dreams/${dreamId}/cancel_undo`, { method: "POST" });
}

export async function completeDreamEarly(dreamId: string | number) {
  return tgFetch(`/api/dreams/${dreamId}/complete`, { method: "POST" });
}

export async function setMainDream(dreamId: string | number) {
  return tgFetch(`/api/dreams/${dreamId}/set_main`, { method: "POST" });
}

// Admin
export async function getAdminDashboard() {
  return tgFetch("/api/mng-x89b2k1q/dashboard");
}

export async function getAdminFinance() {
  return tgFetch("/api/mng-x89b2k1q/finance");
}

export async function getAdminSettings() {
  return tgFetch("/api/mng-x89b2k1q/settings");
}

export async function updateAdminSettings(payload: Record<string, string>) {
  return tgFetch("/api/mng-x89b2k1q/settings", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getAdminPromos() {
  return tgFetch("/api/mng-x89b2k1q/promos");
}

export async function createAdminPromo(code: string, days: number, maxUses: number) {
  return tgFetch("/api/mng-x89b2k1q/promos", {
    method: "POST",
    body: JSON.stringify({ code, days, max_uses: maxUses }),
  });
}

export async function deleteAdminPromo(id: number | string) {
  return tgFetch(`/api/mng-x89b2k1q/promos/${id}`, { method: "DELETE" });
}

export async function searchAdminUser(telegramId: string | number) {
  return tgFetch("/api/mng-x89b2k1q/users/search", {
    method: "POST",
    body: JSON.stringify({ telegram_id: telegramId }),
  });
}

export async function toggleAdminFreeze(telegramId: string | number) {
  return tgFetch("/api/mng-x89b2k1q/users/toggle_freeze", {
    method: "POST",
    body: JSON.stringify({ telegram_id: telegramId }),
  });
}

export async function archiveAdminUser(telegramId: string | number) {
  return tgFetch(`/api/mng-x89b2k1q/users/${telegramId}`, { method: "DELETE" });
}

export async function requestUserHardDelete(telegramId: string | number) {
  return tgFetch(`/api/mng-x89b2k1q/users/request_delete/${telegramId}`, { method: "POST" });
}

export async function getAdminCancelRequests() {
  return tgFetch("/api/mng-x89b2k1q/moderation/cancel_requests");
}

export async function confirmAdminDreamCancel(telegramId: string | number, dreamId: string | number) {
  return tgFetch("/api/mng-x89b2k1q/dreams/cancel_confirm", {
    method: "POST",
    body: JSON.stringify({ telegram_id: telegramId, dream_id: dreamId }),
  });
}

export async function broadcastAdminMessage(message: string) {
  return tgFetch("/api/mng-x89b2k1q/broadcast", {
    method: "POST",
    body: JSON.stringify({ message }),
  });
}

export async function getAdminReferralsStats() {
  return tgFetch("/api/mng-x89b2k1q/referrals/stats");
}

export async function getAdminUserReferrals(telegramId: string | number, page: number) {
  return tgFetch(`/api/mng-x89b2k1q/users/${telegramId}/referrals?page=${page}`);
}

// Settings
export async function updateLanguage(userId: string | number, lang: string) {
  return tgFetch(`/api/settings/lang/${userId}`, {
    method: "POST",
    body: JSON.stringify({ lang }),
  });
}

export async function updateBaseCurrency(userId: string | number, currency: string) {
  return tgFetch(`/api/settings/base_currency/${userId}`, {
    method: "POST",
    body: JSON.stringify({ base_currency: currency }),
  });
}

export async function requestHelp(userId: string | number) {
  return tgFetch(`/api/help/${userId}`, { method: "POST" });
}

