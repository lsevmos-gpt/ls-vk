// ЛИНИЯ СПОРТА · СВЕТ — v3.0
// Три клуба + подтверждаемое действие «Все клубы».
// Только D1: публикации в Instagram и VK ВЫКЛЮЧЕНЫ.
// Зависимости: Secret TELEGRAM_BOT_TOKEN, D1 binding DB.
const WEBHOOK_PATH = "/telegram/webhook";
const CLUB_IDS = ["heroes6d", "konnaya25", "kuib60"];
const BULK_IDS = "'heroes6d','konnaya25','kuib60'";

function json(value, status = 200) {
  return new Response(JSON.stringify(value), {
    status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Cache-Control": "no-store",
    },
  });
}

async function secretFromBotToken(token) {
  // Нельзя изменять: такой секрет используется в уже действующем webhook.
  const bytes = new TextEncoder().encode("ls-light-bot:" + token);
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest), b => b.toString(16).padStart(2, "0")).join("");
}

async function tg(env, method, params = {}) {
  const res = await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/${method}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  const data = await res.json();
  if (!res.ok || !data.ok) throw new Error(`${method}: ${data.description || res.status}`);
  return data.result;
}

function statusLabel(value) {
  return ({ on: "🟢 Свет есть", off: "🔴 Света нет", unknown: "⚪ Неизвестно" })[value] || "⚪ Неизвестно";
}

async function getUser(db, telegramId) {
  return db.prepare("SELECT telegram_id, role FROM admins WHERE telegram_id = ? AND active = 1")
    .bind(telegramId).first();
}

async function getVisible(db, user) {
  const sql = `SELECT c.id, c.name, c.status, c.stories_ready FROM clubs c
    WHERE c.id IN (${BULK_IDS}) AND
       (? = 'owner' OR EXISTS (
          SELECT 1 FROM admin_clubs a WHERE a.club_id = c.id AND a.telegram_id = ?
        ))
    ORDER BY CASE c.id
      WHEN 'heroes6d' THEN 1 WHEN 'konnaya25' THEN 2 WHEN 'kuib60' THEN 3 END`;
  return (await db.prepare(sql).bind(user.role, user.telegram_id).all()).results;
}

async function allowedClub(db, user, clubId) {
  if (!CLUB_IDS.includes(clubId)) return null;
  return db.prepare(`SELECT c.id, c.name, c.status, c.stories_ready FROM clubs c
    WHERE c.id = ? AND
      (? = 'owner' OR EXISTS (
        SELECT 1 FROM admin_clubs a WHERE a.club_id = c.id AND a.telegram_id = ?
      ))`).bind(clubId, user.role, user.telegram_id).first();
}

function allAccess(user, visible) {
  return user.role === "owner" && CLUB_IDS.every(id => visible.some(c => c.id === id)) ||
    CLUB_IDS.every(id => visible.some(c => c.id === id));
}

function menuView(user, clubs) {
  const lines = ["🏋️ ЛИНИЯ СПОРТА · СВЕТ", "", "Выберите клуб:", ""];
  clubs.forEach(c => lines.push(`${statusLabel(c.status)} — ${c.name}`));
  lines.push("", "🧪 Тестовый режим: сторис не публикуются.");
  const keyboard = clubs.map(c => [{ text: c.name, callback_data: `club:${c.id}` }]);
  if (allAccess(user, clubs)) keyboard.push([{ text: "🌐 Все клубы", callback_data: "all" }]);
  return { text: lines.join("\n"), keyboard };
}

function clubView(club) {
  return {
    text: [
      `🏋️ ${club.name}`, "", `Сейчас: ${statusLabel(club.status)}`, "",
      "Выберите состояние:", "", "🧪 Изменяется только база D1. Публикация выключена.",
    ].join("\n"),
    keyboard: [
      [{ text: "🟢 Свет есть", callback_data: `set:${club.id}:on` }],
      [{ text: "🔴 Света нет", callback_data: `set:${club.id}:off` }],
      [{ text: "⬅️ К списку клубов", callback_data: "menu" }],
    ],
  };
}

function allView(clubs) {
  const lines = ["🌐 ВСЕ КЛУБЫ", "", "Актуальные статусы:"];
  clubs.forEach(c => lines.push(`${statusLabel(c.status)} — ${c.name}`));
  lines.push("", "Команда изменит данные СРАЗУ во всех трёх клубах.");
  lines.push("Выбор потребует отдельного подтверждения.");
  lines.push("", "🧪 Публикации отключены.");
  return {
    text: lines.join("\n"),
    keyboard: [
      [{ text: "🟢 Свет есть во всех", callback_data: "allpick:on" }],
      [{ text: "🔴 Света нет во всех", callback_data: "allpick:off" }],
      [{ text: "⬅️ К списку клубов", callback_data: "menu" }],
    ],
  };
}

function confirmAllView(state) {
  return {
    text: [
      "⚠️ ПОДТВЕРЖДЕНИЕ ДЛЯ ВСЕХ КЛУБОВ", "",
      `Команда: ${statusLabel(state)} — ВО ВСЕХ ТРЁХ КЛУБАХ.`,
      "", "Героев Сталинграда, 6Д", "1-й Конной Армии, 25А", "Куйбышева, 60",
      "", "Вы лично подтверждаете наличие этого состояния во всех трёх залах?",
      "", "🧪 Сейчас меняем только базу, без соцсетей.",
    ].join("\n"),
    keyboard: [
      [{ text: `✅ Подтвердить: ${state === "on" ? "свет есть" : "света нет"}`, callback_data: `allset:${state}` }],
      [{ text: "Отмена", callback_data: "all" }],
    ],
  };
}

async function render(env, chatId, messageId, view) {
  const args = {
    chat_id: chatId,
    text: view.text,
    reply_markup: { inline_keyboard: view.keyboard },
  };
  if (messageId == null) return tg(env, "sendMessage", args);
  try {
    return await tg(env, "editMessageText", { ...args, message_id: messageId });
  } catch (e) {
    // Повторная доставка/нажатие не должна вызывать бесконечные повторы webhook.
    if (String(e.message).toLowerCase().includes("message is not modified")) return;
    throw e;
  }
}

async function answer(env, id, text = "", alert = false) {
  return tg(env, "answerCallbackQuery", {
    callback_query_id: id,
    ...(text ? { text } : {}),
    ...(alert ? { show_alert: true } : {}),
  });
}

async function ensureUpdates(env) {
  // Не меняем webhook URL и сохранённый секрет. Кнопки уже работали в v2.
  const info = await tg(env, "getWebhookInfo");
  if (!info.url) throw new Error("Telegram webhook не зарегистрирован");
  if (!Array.isArray(info.allowed_updates) || !info.allowed_updates.includes("callback_query")) {
    await tg(env, "setWebhook", {
      url: info.url,
      secret_token: await secretFromBotToken(env.TELEGRAM_BOT_TOKEN),
      allowed_updates: ["message", "callback_query"],
    });
  }
}

async function onMessage(msg, env) {
  if (msg.chat?.type !== "private") return;
  const user = await getUser(env.DB, msg.from?.id);
  if (!user) {
    await tg(env, "sendMessage", {
      chat_id: msg.chat.id,
      text: `⛔ Нет доступа к управлению светом.\nTelegram ID: ${msg.from?.id}\nОбратитесь к руководителю.`,
    });
    return;
  }
  const command = (msg.text || "").trim().split(/\s+/)[0].split("@")[0];
  if (command === "/start" && user.role === "owner") {
    try { await ensureUpdates(env); }
    catch (e) { console.error("Обновление webhook:", e.message); }
  }
  await render(env, msg.chat.id, null, menuView(user, await getVisible(env.DB, user)));
}

// Каждая команда имеет уникальный ID Telegram callback. Благодаря этому повторная
// доставка того же webhook не сможет повторно изменить состояние, даже если
// другой сотрудник уже успел изменить его обратно.
async function applyChange(db, user, operationId, scope, clubId, state) {
  if (!/^(on|off)$/.test(state)) throw new Error("Некорректное состояние");
  const isBulk = scope === "all";
  const where = isBulk ? `c.id IN (${BULK_IDS})` : "c.id = ?";
  const filterArgs = isBulk ? [] : [clubId];
  const inserted = db.prepare(`INSERT OR IGNORE INTO light_operations
    (operation_id, telegram_id, scope, club_id, new_status)
    VALUES (?, ?, ?, ?, ?)`).bind(operationId, user.telegram_id, scope,
      isBulk ? null : clubId, state);

  const collect = db.prepare(`INSERT INTO light_operation_changes
     (operation_id, club_id, old_status, new_status)
     SELECT ?, c.id, c.status, ? FROM clubs c
     WHERE ${where} AND c.status <> ? AND EXISTS (
       SELECT 1 FROM light_operations o
       WHERE o.operation_id = ? AND o.processed = 0
     )`).bind(operationId, state, ...filterArgs, state, operationId);

  const history = db.prepare(`INSERT INTO status_events
     (club_id, telegram_id, old_status, new_status)
     SELECT oc.club_id, ?, oc.old_status, oc.new_status
     FROM light_operation_changes oc
     WHERE oc.operation_id = ? AND EXISTS (
       SELECT 1 FROM light_operations o
       WHERE o.operation_id = ? AND o.processed = 0
     )`).bind(user.telegram_id, operationId, operationId);

  const apply = db.prepare(`UPDATE clubs SET
       status = ?, changed_at = CURRENT_TIMESTAMP, changed_by = ?
     WHERE id IN (SELECT club_id FROM light_operation_changes
       WHERE operation_id = ?)
       AND EXISTS (SELECT 1 FROM light_operations
         WHERE operation_id = ? AND processed = 0)`)
    .bind(state, user.telegram_id, operationId, operationId);

  const finalize = db.prepare(`UPDATE light_operations
      SET processed = 1,
          changed_count = (SELECT COUNT(*) FROM light_operation_changes
                           WHERE operation_id = ?)
      WHERE operation_id = ? AND processed = 0`)
    .bind(operationId, operationId);

  // D1 batch() выполняется атомарно: либо все пять шагов, либо ни одного.
  await db.batch([inserted, collect, history, apply, finalize]);
  return db.prepare("SELECT changed_count FROM light_operations WHERE operation_id = ?")
    .bind(operationId).first();
}

async function onCallback(callback, env) {
  if (callback.message?.chat?.type !== "private") return;
  const user = await getUser(env.DB, callback.from?.id);
  if (!user) return answer(env, callback.id, "Нет доступа", true);

  const chatId = callback.message.chat.id;
  const messageId = callback.message.message_id;
  const data = String(callback.data || "");
  const clubs = await getVisible(env.DB, user);
  const canAll = allAccess(user, clubs);

  if (data === "menu") {
    await answer(env, callback.id);
    return render(env, chatId, messageId, menuView(user, clubs));
  }
  if (data === "all" || data.startsWith("allpick:") || data.startsWith("allset:")) {
    if (!canAll) return answer(env, callback.id, "Нет доступа ко всем клубам", true);
    if (data === "all") {
      await answer(env, callback.id);
      return render(env, chatId, messageId, allView(clubs));
    }
    if (data === "allpick:on" || data === "allpick:off") {
      await answer(env, callback.id);
      return render(env, chatId, messageId, confirmAllView(data.split(":")[1]));
    }
    if (data !== "allset:on" && data !== "allset:off") return answer(env, callback.id, "Неверная команда");
    const state = data.split(":")[1];
    const op = await applyChange(env.DB, user, callback.id, "all", null, state);
    const changed = Number(op?.changed_count || 0);
    await answer(env, callback.id,
      changed ? `Обновлено клубов: ${changed} из 3` : "У всех клубов уже этот статус");
    const updated = await getVisible(env.DB, user);
    return render(env, chatId, messageId, allView(updated));
  }

  const pieces = data.split(":");
  const [action, clubId, state] = pieces;
  if (pieces.length < 2 || pieces.length > 3 || !["club", "set"].includes(action)) {
    return answer(env, callback.id, "Неверная команда");
  }
  const club = await allowedClub(env.DB, user, clubId);
  if (!club) return answer(env, callback.id, "Нет доступа к клубу", true);
  if (action === "club" && pieces.length === 2) {
    await answer(env, callback.id);
    return render(env, chatId, messageId, clubView(club));
  }
  if (action !== "set" || !["on", "off"].includes(state) || pieces.length !== 3) {
    return answer(env, callback.id, "Неверная команда");
  }
  const op = await applyChange(env.DB, user, callback.id, "club", clubId, state);
  const changed = Number(op?.changed_count || 0);
  await answer(env, callback.id, changed ? "Состояние сохранено" : "Статус не изменился");
  const updated = await allowedClub(env.DB, user, clubId);
  return render(env, chatId, messageId, clubView(updated));
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (request.method === "GET" && url.pathname === "/") {
      return json({ status: "ok", service: "ls-light-bot", version: 3, publishingEnabled: false });
    }
    if (request.method !== "POST" || url.pathname !== WEBHOOK_PATH) {
      return json({ error: "not_found" }, 404);
    }
    if (!env.TELEGRAM_BOT_TOKEN || !env.DB) return json({ error: "not_configured" }, 503);
    const incoming = request.headers.get("X-Telegram-Bot-Api-Secret-Token");
    if (incoming !== await secretFromBotToken(env.TELEGRAM_BOT_TOKEN)) {
      return json({ error: "forbidden" }, 403);
    }
    let update;
    try { update = await request.json(); }
    catch { return json({ error: "invalid_json" }, 400); }
    try {
      if (update.message) await onMessage(update.message, env);
      if (update.callback_query) await onCallback(update.callback_query, env);
      return json({ ok: true });
    } catch (e) {
      console.error("Ошибка Telegram / D1:", e.message);
      return json({ error: "temporary_failure" }, 500);
    }
  },
};