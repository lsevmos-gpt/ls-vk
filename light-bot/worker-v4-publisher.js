// ЛИНИЯ СПОРТА · СВЕТ — v3.1 (owner-only read-only API diagnostics)
// Три клуба + подтверждаемое действие «Все клубы».
// D1 + диагностика + безопасная очередь публикаций. Две защиты по умолчанию ВЫКЛЮЧЕНЫ.
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

function menuView(user, clubs, live = false) {
  const lines = ["🏋️ ЛИНИЯ СПОРТА · СВЕТ", "", "Выберите клуб:", ""];
  clubs.forEach(c => lines.push(`${statusLabel(c.status)} — ${c.name}`));
  lines.push("", live ? "📤 Изменение статуса запускает публикацию." : "🧪 Тестовый режим: сторис не публикуются.");
  const keyboard = clubs.map(c => [{ text: c.name, callback_data: `club:${c.id}` }]);
  if (allAccess(user, clubs)) keyboard.push([{ text: "🌐 Все клубы", callback_data: "all" }]);
  return { text: lines.join("\n"), keyboard };
}

function clubView(club, live = false) {
  return {
    text: [
      `🏋️ ${club.name}`, "", `Сейчас: ${statusLabel(club.status)}`, "",
      "Выберите состояние:", "", live ? "📤 Изменение статуса запускает публикацию." : "🧪 Изменяется только база D1. Публикация выключена.",
    ].join("\n"),
    keyboard: [
      [{ text: "🟢 Свет есть", callback_data: `set:${club.id}:on` }],
      [{ text: "🔴 Света нет", callback_data: `set:${club.id}:off` }],
      [{ text: "⬅️ К списку клубов", callback_data: "menu" }],
    ],
  };
}

function allView(clubs, live = false) {
  const lines = ["🌐 ВСЕ КЛУБЫ", "", "Актуальные статусы:"];
  clubs.forEach(c => lines.push(`${statusLabel(c.status)} — ${c.name}`));
  lines.push("", "Команда изменит данные СРАЗУ во всех трёх клубах.");
  lines.push("Выбор потребует отдельного подтверждения.");
  lines.push("", live ? "📤 При изменении публикуется одна общая сторис в каждой сети." : "🧪 Публикации отключены.");
  return {
    text: lines.join("\n"),
    keyboard: [
      [{ text: "🟢 Свет есть во всех", callback_data: "allpick:on" }],
      [{ text: "🔴 Света нет во всех", callback_data: "allpick:off" }],
      [{ text: "⬅️ К списку клубов", callback_data: "menu" }],
    ],
  };
}

function confirmAllView(state, live = false) {
  return {
    text: [
      "⚠️ ПОДТВЕРЖДЕНИЕ ДЛЯ ВСЕХ КЛУБОВ", "",
      `Команда: ${statusLabel(state)} — ВО ВСЕХ ТРЁХ КЛУБАХ.`,
      "", "Героев Сталинграда, 6Д", "1-й Конной Армии, 25А", "Куйбышева, 60",
      "", "Вы лично подтверждаете наличие этого состояния во всех трёх залах?",
      "", live ? "📤 После подтверждения отправим одну общую сторис в каждую сеть." : "🧪 Сейчас меняем только базу, без соцсетей.",
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


// --- Owner-only read-only diagnostics: no publishing, no token exposure ---
const EXPECTED_VK_ID = "48198173";
const EXPECTED_VK_NAME = "liniya__sporta";
const EXPECTED_IG_ID = "17841458490047255";
const EXPECTED_IG_NAME = "liniya__sporta";
const EXPECTED_PAGE_ID = "1309947522200598";

function errorHint(code) {
  if (code === "missing") return "не задан токен / ID";
  if (code === "network") return "нет ответа от API";
  return "ошибка API " + String(code || "unknown").slice(0, 12);
}

async function metaRead(env, objectId, fields) {
  if (!env.META_IG_ACCESS_TOKEN) return { ok: false, code: "missing" };
  try {
    const url = "https://graph.facebook.com/v26.0/" + objectId +
      "?fields=" + encodeURIComponent(fields);
    const response = await fetch(url, {
      method: "GET",
      headers: { Authorization: "Bearer " + env.META_IG_ACCESS_TOKEN },
      signal: AbortSignal.timeout(9000),
    });
    const data = await response.json();
    if (!response.ok || data.error) {
      return { ok: false, code: Number(data.error?.code || response.status) };
    }
    return { ok: true, data };
  } catch {
    return { ok: false, code: "network" };
  }
}

async function vkRead(env, method, fields = {}) {
  if (!env.VK_GROUP_TOKEN) return { ok: false, code: "missing" };
  const body = new URLSearchParams({
    ...fields,
    access_token: env.VK_GROUP_TOKEN,
    v: "5.199",
  });
  try {
    const response = await fetch("https://api.vk.ru/method/" + method, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body,
      signal: AbortSignal.timeout(9000),
    });
    const data = await response.json();
    if (!response.ok || data.error) {
      return { ok: false, code: Number(data.error?.error_code || response.status) };
    }
    return { ok: true, data: data.response };
  } catch {
    return { ok: false, code: "network" };
  }
}

async function diagnosticMessage(env) {
  const lines = ["🔎 ЛИНИЯ СПОРТА · ПРОВЕРКА API", ""];
  if (String(env.VK_GROUP_ID || "") !== EXPECTED_VK_ID) {
    lines.push("❌ VK: неверный или отсутствующий VK_GROUP_ID");
  } else {
    const group = await vkRead(env, "groups.getById", { group_id: EXPECTED_VK_ID });
    if (!group.ok) {
      lines.push("❌ VK: " + errorHint(group.code));
    } else {
      const target = Array.isArray(group.data)
        ? group.data[0]
        : Array.isArray(group.data?.groups)
          ? group.data.groups[0]
          : group.data;
      if (String(target?.id) !== EXPECTED_VK_ID ||
          target?.screen_name !== EXPECTED_VK_NAME) {
        lines.push("❌ VK: ответ не соответствует сообществу «Линия спорта»");
      } else {
        lines.push("✅ VK: сообщество подтверждено");
        const upload = await vkRead(env, "stories.getPhotoUploadServer", {
          group_id: EXPECTED_VK_ID, add_to_news: "0",
        });
        if (upload.ok && upload.data?.upload_url) {
          lines.push("✅ VK Stories: сервер загрузки доступен");
        } else {
          lines.push("❌ VK Stories: " +
            (upload.ok ? "нет адреса загрузки" : errorHint(upload.code)));
        }
      }
    }
  }

  if (String(env.META_IG_USER_ID || "") !== EXPECTED_IG_ID) {
    lines.push("❌ Instagram: неверный или отсутствующий META_IG_USER_ID");
  } else {
    const [page, instagram] = await Promise.all([
      metaRead(env, EXPECTED_PAGE_ID, "id,name,instagram_business_account"),
      metaRead(env, EXPECTED_IG_ID, "id,username"),
    ]);
    if (!page.ok) lines.push("❌ Meta Page: " + errorHint(page.code));
    else if (String(page.data?.id) !== EXPECTED_PAGE_ID ||
             String(page.data?.instagram_business_account?.id) !== EXPECTED_IG_ID) {
      lines.push("❌ Meta Page: неверная привязка Instagram");
    } else lines.push("✅ Meta Page: подтверждена привязка Instagram");

    if (!instagram.ok) lines.push("❌ Instagram: " + errorHint(instagram.code));
    else if (String(instagram.data?.id) !== EXPECTED_IG_ID ||
             instagram.data?.username !== EXPECTED_IG_NAME) {
      lines.push("❌ Instagram: ID или имя аккаунта не совпадают");
    } else lines.push("✅ Instagram: @liniya__sporta подтверждён");
  }
  lines.push("", "🔒 Токены в ответе не отображаются.");
  lines.push("🧪 Публикация сторис выключена.");
  lines.push("Проверка API не является тестовой публикацией.");
  return lines.join("\n");
}

// --- Публикация сторис: очередь D1, резервная обработка Cloudflare Cron. ---
// ВНИМАНИЕ: по умолчанию ВЫКЛЮЧЕНА двумя независимыми настройками.
const LIGHT_ASSETS_ORIGIN = "https://ls-light-medi.pages.dev";
const LIGHT_ASSET_KEYS = new Set([
  "heroes6d-on", "heroes6d-off", "konnaya25-on", "konnaya25-off",
  "kuib60-on", "kuib60-off", "all-on", "all-off"
]);
const PUBLISHABLE_STATES = ["queued", "processing", "ready", "submitted"];

async function publishingEnabled(env) {
  if (String(env.PUBLISH_ENABLED || "").toLowerCase() !== "true") return false;
  const setting = await env.DB.prepare("SELECT enabled FROM light_publish_settings WHERE id = 1").first();
  return Number(setting?.enabled) === 1;
}

function assetURL(job) {
  if (!LIGHT_ASSET_KEYS.has(job.asset_key)) throw Error("invalid_asset_key");
  return LIGHT_ASSETS_ORIGIN + "/media/light/" + job.asset_key +
    (job.platform === "instagram" ? ".jpg" : ".png");
}

async function markState(db, job, from, to, extra = {}) {
  const allowed = new Set([
    "state", "container_id", "upload_result", "external_id",
    "diagnostic", "verification_attempts"
  ]);
  if (!Object.keys(extra).every(k => allowed.has(k) && k !== "state")) throw Error("invalid_db_update");
  const fields = ["state = ?", "updated_at = CURRENT_TIMESTAMP",
    ...Object.keys(extra).map(k => k + " = ?")];
  const args = [to, ...Object.values(extra), job.job_id, from];
  const stmt = db.prepare("UPDATE light_publication_jobs SET " + fields.join(", ") +
    " WHERE job_id = ? AND state = ?");
  const r = await stmt.bind(...args).run();
  return Number(r.meta?.changes || 0) === 1;
}

async function isLatestOperation(db, job) {
  // Уже отменённое/устаревшее задание не должно создать сторис.
  const q = `SELECT COUNT(*) AS cnt
    FROM light_operations newer
    JOIN light_operation_changes oc ON oc.operation_id = newer.operation_id
    WHERE newer.rowid > (SELECT rowid FROM light_operations WHERE operation_id = ?)
      AND oc.club_id IN (${job.scope === "all" ? BULK_IDS : "?"})`;
  const row = await db.prepare(q).bind(job.operation_id,
    ...(job.scope === "all" ? [] : [job.club_id])).first();
  if (Number(row?.cnt || 0) > 0) return false;
  const clubs = await db.prepare(`SELECT id, status FROM clubs
    WHERE id IN (${job.scope === "all" ? BULK_IDS : "?"})`)
    .bind(...(job.scope === "all" ? [] : [job.club_id])).all();
  return clubs.results.length === (job.scope === "all" ? 3 : 1) &&
    clubs.results.every(c => c.status === job.new_status);
}

function isValidHTTPS(u) {
  try {
    const url = new URL(u);
    return url.protocol === "https:";
  } catch { return false; }
}

async function httpResult(response, provider) {
  // Никогда не логируем ответ целиком (там могут быть персональные данные).
  let j;
  try { j = await response.json(); }
  catch { throw Error(provider + "_invalid_json"); }
  if (!response.ok || j.error) {
    throw Error(provider + "_code_" + String(j.error?.code || j.error?.error_code || response.status));
  }
  return j;
}

async function metaApi(env, method, path, fields = null) {
  if (!env.META_IG_ACCESS_TOKEN || !env.META_IG_USER_ID) throw Error("meta_missing_credentials");
  const base = "https://graph.facebook.com/v26.0/" + path;
  const qs = method === "GET" && fields ? "?" + new URLSearchParams(fields) : "";
  const response = await fetch(base + qs, {
    method,
    headers: {
      Authorization: "Bearer " + env.META_IG_ACCESS_TOKEN,
      ...(method === "POST" ? { "Content-Type": "application/x-www-form-urlencoded" } : {})
    },
    ...(method === "POST" ? { body: new URLSearchParams(fields || {}) } : {}),
    signal: AbortSignal.timeout(17000),
  });
  return httpResult(response, "meta");
}

async function vkApi(env, method, fields = {}) {
  if (!env.VK_GROUP_TOKEN) throw Error("vk_missing_credentials");
  const response = await fetch("https://api.vk.ru/method/" + method, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({ ...fields, access_token: env.VK_GROUP_TOKEN, v: "5.199" }),
    signal: AbortSignal.timeout(17000),
  });
  const data = await httpResult(response, "vk");
  return data.response;
}

async function verifyMetaTarget(env) {
  const account = await metaApi(env, "GET", EXPECTED_IG_ID, { fields: "id,username" });
  if (String(account.id) !== EXPECTED_IG_ID || account.username !== EXPECTED_IG_NAME) {
    throw Error("meta_wrong_ig_account");
  }
}

async function verifyVkTarget(env) {
  const result = await vkApi(env, "groups.getById", { group_id: EXPECTED_VK_ID });
  const group = Array.isArray(result) ? result[0] : (result?.groups?.[0] || result);
  if (String(group?.id) !== EXPECTED_VK_ID || group?.screen_name !== EXPECTED_VK_NAME) {
    throw Error("vk_wrong_group");
  }
}

async function fetchImage(url, format) {
  const res = await fetch(url, { method: "GET", signal: AbortSignal.timeout(14000) });
  if (!res.ok) throw Error("asset_http_" + res.status);
  const data = await res.arrayBuffer();
  const type = (res.headers.get("content-type") || "").toLowerCase();
  if (data.byteLength < 10_000 || data.byteLength > 15_000_000 ||
      !type.includes(format === "jpg" ? "image/jpeg" : "image/png")) {
    throw Error("asset_invalid_type_or_size");
  }
  return new Blob([data], { type: format === "jpg" ? "image/jpeg" : "image/png" });
}

async function createMetaContainer(env, job) {
  await verifyMetaTarget(env);
  const img = assetURL(job);
  // Проверка наличия файла, без создания сторис.
  await fetchImage(img, "jpg");
  const r = await metaApi(env, "POST", EXPECTED_IG_ID + "/media", {
    media_type: "STORIES", image_url: img
  });
  if (!/^\d+$/.test(String(r.id || ""))) throw Error("meta_no_container_id");
  return String(r.id);
}

async function uploadVkPhoto(env, job) {
  await verifyVkTarget(env);
  const photo = await fetchImage(assetURL(job), "png");
  const server = await vkApi(env, "stories.getPhotoUploadServer", {
    group_id: EXPECTED_VK_ID, add_to_news: "1"
  });
  if (!isValidHTTPS(server?.upload_url)) throw Error("vk_invalid_upload_url");
  // URL загрузки выдаётся официальным API VK.
  const url = new URL(server.upload_url);
  if (!/(^|\.)vk\.(ru|com)$/.test(url.hostname)) throw Error("vk_invalid_upload_host");
  const form = new FormData();
  form.append("file", photo, job.asset_key + ".png");
  const response = await fetch(url, {
    method: "POST", body: form, signal: AbortSignal.timeout(17000)
  });
  const result = await httpResult(response, "vk_upload");
  const value = result?.response?.upload_result ?? result?.response?.upload_results ??
    result?.upload_result ?? result?.upload_results;
  const prepared = Array.isArray(value) ? value[0] : value;
  if (!prepared) throw Error("vk_upload_result_missing");
  if (typeof prepared !== "string") throw Error("vk_upload_result_unexpected_type");
  return prepared;
}

async function confirmVkStory(env, storyId) {
  try {
    const response = await vkApi(env, "stories.get", { owner_id: "-" + EXPECTED_VK_ID });
    const raw = Array.isArray(response?.items) ? response.items : Array.isArray(response) ? response : [];
    const items = raw.flatMap(x => Array.isArray(x?.stories) ? x.stories : Array.isArray(x) ? x : [x]);
    return items.some(x => String(x?.owner_id) === "-" + EXPECTED_VK_ID && String(x?.id) === String(storyId));
  } catch { return false; }
}

async function advanceJob(env, job) {
  const db = env.DB;
  if (["queued", "processing", "ready"].includes(job.state) &&
      !(await isLatestOperation(db, job))) {
    await markState(db, job, job.state, "superseded", { diagnostic: "newer_status" });
    return "done";
  }

  if (job.state === "queued") {
    if (!await markState(db, job, "queued", "preparing")) return "done";
    try {
      if (job.platform === "instagram") {
        const container = await createMetaContainer(env, job);
        await markState(db, job, "preparing", "processing", { container_id: container });
      } else {
        const uploadResult = await uploadVkPhoto(env, job);
        await markState(db, job, "preparing", "ready", { upload_result: uploadResult });
      }
    } catch (err) {
      // На этом этапе готовые сторис ещё не публиковались.
      await markState(db, job, "preparing", "review_required", { diagnostic: String(err.message).slice(0,90) });
    }
    return "more";
  }

  if (job.state === "processing") {
    try {
      const r = await metaApi(env, "GET", job.container_id, { fields: "status_code,status" });
      const state = String(r.status_code || "");
      if (state === "FINISHED") {
        await markState(db, job, "processing", "ready");
        return "more";
      }
      if (["ERROR", "EXPIRED"].includes(state)) {
        await markState(db, job, "processing", "failed", { diagnostic: "container_" + state });
        return "done";
      }
      return "wait";
    } catch { return "wait"; }
  }

  if (job.state === "ready") {
    // Предохранитель от повторной публикации: состояние publishing фиксируется
    // ДО необратимого API-запроса. Никаких автоматических повторов этого вызова.
    if (!await markState(db, job, "ready", "publishing")) return "done";
    try {
      if (job.platform === "instagram") {
        const r = await metaApi(env, "POST", EXPECTED_IG_ID + "/media_publish", {
          creation_id: job.container_id
        });
        if (!/^\d+$/.test(String(r.id || ""))) throw Error("meta_publish_no_media_id");
        await markState(db, job, "publishing", "submitted", { external_id: String(r.id) });
      } else {
        const r = await vkApi(env, "stories.save", { upload_results: job.upload_result });
        const story = Array.isArray(r?.items) ? r.items.find(x =>
          String(x?.owner_id) === "-" + EXPECTED_VK_ID && /^\d+$/.test(String(x?.id || ""))) : null;
        if (!story) throw Error("vk_save_no_matching_story_id");
        await markState(db, job, "publishing", "submitted", { external_id: String(story.id) });
      }
      return "more";
    } catch (err) {
      // Невозможно отличить сетевую ошибку от успешного постинга без readback.
      // Не повторять запрос; требуется ручная проверка.
      await markState(db, job, "publishing", "review_required", {
        diagnostic: "uncertain_" + String(err.message).slice(0,72)
      });
      return "done";
    }
  }

  if (job.state === "submitted") {
    let valid = false;
    try {
      if (job.platform === "instagram") {
        const info = await metaApi(env, "GET", job.external_id, { fields: "id,media_type,timestamp,permalink" });
        valid = String(info.id) === String(job.external_id);
      } else valid = await confirmVkStory(env, job.external_id);
    } catch { valid = false; }
    if (valid) {
      await markState(db, job, "submitted", "published");
      return "done";
    }
    const attempts = Number(job.verification_attempts || 0) + 1;
    if (attempts >= 5) {
      await markState(db, job, "submitted", "review_required", {
        verification_attempts: attempts, diagnostic: "published_readback_not_confirmed"
      });
      return "done";
    }
    await markState(db, job, "submitted", "submitted", {
      verification_attempts: attempts
    });
    return "wait";
  }
  return "done";
}

async function queueWork(env, maxMs = 17000) {
  if (!await publishingEnabled(env)) return;
  const start = Date.now();
  const paused = new Set();
  for (let i = 0; i < 12 && Date.now() - start < maxMs; i++) {
    const pending = (await env.DB.prepare(`SELECT * FROM light_publication_jobs
      WHERE state IN ('queued','processing','ready','submitted')
      ORDER BY created_at, job_id LIMIT 30`).all()).results;
    const job = pending.find(item => !paused.has(item.job_id));
    if (!job) return;
    const outcome = await advanceJob(env, job);
    // Пока Meta обрабатывает контейнер, не блокировать VK и другие задания.
    if (outcome === "wait") paused.add(job.job_id);
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
  if (command === "/check") {
    if (user.role !== "owner") {
      await tg(env, "sendMessage", {
        chat_id: msg.chat.id, text: "⛔ Команда доступна только владельцу.",
      });
      return;
    }
    await tg(env, "sendMessage", {
      chat_id: msg.chat.id,
      text: await diagnosticMessage(env),
    });
    return;
  }
  if (command === "/start" && user.role === "owner") {
    try { await ensureUpdates(env); }
    catch (e) { console.error("Обновление webhook:", e.message); }
  }
  await render(env, msg.chat.id, null, menuView(user, await getVisible(env.DB, user), await publishingEnabled(env)));
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
    return render(env, chatId, messageId, menuView(user, clubs, await publishingEnabled(env)));
  }
  if (data === "all" || data.startsWith("allpick:") || data.startsWith("allset:")) {
    if (!canAll) return answer(env, callback.id, "Нет доступа ко всем клубам", true);
    if (data === "all") {
      await answer(env, callback.id);
      return render(env, chatId, messageId, allView(clubs, await publishingEnabled(env)));
    }
    if (data === "allpick:on" || data === "allpick:off") {
      await answer(env, callback.id);
      return render(env, chatId, messageId, confirmAllView(data.split(":")[1], await publishingEnabled(env)));
    }
    if (data !== "allset:on" && data !== "allset:off") return answer(env, callback.id, "Неверная команда");
    const state = data.split(":")[1];
    const op = await applyChange(env.DB, user, callback.id, "all", null, state);
    const changed = Number(op?.changed_count || 0);
    await answer(env, callback.id,
      changed ? `Обновлено клубов: ${changed} из 3` : "У всех клубов уже этот статус");
    const updated = await getVisible(env.DB, user);
    return render(env, chatId, messageId, allView(updated, await publishingEnabled(env)));
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
    return render(env, chatId, messageId, clubView(club, await publishingEnabled(env)));
  }
  if (action !== "set" || !["on", "off"].includes(state) || pieces.length !== 3) {
    return answer(env, callback.id, "Неверная команда");
  }
  const op = await applyChange(env.DB, user, callback.id, "club", clubId, state);
  const changed = Number(op?.changed_count || 0);
  await answer(env, callback.id, changed ? "Состояние сохранено" : "Статус не изменился");
  const updated = await allowedClub(env.DB, user, clubId);
  return render(env, chatId, messageId, clubView(updated, await publishingEnabled(env)));
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    if (request.method === "GET" && url.pathname === "/") {
      return json({ status: "ok", service: "ls-light-bot", version: "4.0", publishingEnabled: await publishingEnabled(env) });
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
      // Событие сохранено; фоновой запуск ускоряет публикацию, Cron — резерв.
      if (update.callback_query && ctx?.waitUntil) {
        ctx.waitUntil(queueWork(env).catch(e => console.error("Light queue:", String(e.message).slice(0,95))));
      }
      return json({ ok: true });
    } catch (e) {
      console.error("Ошибка Telegram / D1:", e.message);
      return json({ error: "temporary_failure" }, 500);
    }
  },
  async scheduled(_controller, env, ctx) {
    ctx.waitUntil(queueWork(env, 25000).catch(e => console.error("Light Cron:", String(e.message).slice(0,95))));
  },
};