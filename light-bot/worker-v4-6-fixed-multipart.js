// ЛИНИЯ СПОРТА · СВЕТ — v4.6: fixed-length VK upload A/B diagnostic
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
  // Уже опубликованные в Cloudflare Pages JPEG подходят и Instagram, и VK.
  return LIGHT_ASSETS_ORIGIN + "/media/light/" + job.asset_key + ".jpg";
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


// Альтернативный multipart: полный буфер фиксированной длины для VK.
// Содержимое URL загрузки и токены не сохраняются и не логируются.
async function postVkMultipart(uploadUrl, imageBlob, filename, transport = "formdata") {
  let body, headers;
  if (transport === "fixed") {
    if (!/^[a-z0-9-]+\.jpg$/.test(filename)) throw Error("vk_bad_filename");
    const boundary = "----LiniyaLight" + crypto.randomUUID().replace(/-/g, "");
    const encoder = new TextEncoder();
    const prefix = encoder.encode(
      "--" + boundary + "\r\n" +
      'Content-Disposition: form-data; name="file"; filename="' + filename + '"\r\n' +
      "Content-Type: image/jpeg\r\n\r\n"
    );
    const image = new Uint8Array(await imageBlob.arrayBuffer());
    const suffix = encoder.encode("\r\n--" + boundary + "--\r\n");
    body = new Uint8Array(prefix.byteLength + image.byteLength + suffix.byteLength);
    body.set(prefix, 0);
    body.set(image, prefix.byteLength);
    body.set(suffix, prefix.byteLength + image.byteLength);
    headers = { "Content-Type": "multipart/form-data; boundary=" + boundary };
    // Workers автоматически устанавливает Content-Length для Uint8Array body.
  } else {
    body = new FormData();
    body.append("file", imageBlob, filename);
  }
  return fetch(uploadUrl, {
    method: "POST",
    ...(headers ? { headers } : {}),
    body,
    signal: AbortSignal.timeout(22000),
  });
}

async function uploadVkPhoto(env, job) {
  await verifyVkTarget(env);
  const photo = await fetchImage(assetURL(job), "jpg");
  const server = await vkApi(env, "stories.getPhotoUploadServer", {
    group_id: EXPECTED_VK_ID, add_to_news: "1"
  });
  if (!isValidHTTPS(server?.upload_url)) throw Error("vk_invalid_upload_url");
  // URL загрузки выдаётся официальным API VK.
  const url = new URL(server.upload_url);
  if (!/(^|\.)vk\.(ru|com)$/.test(url.hostname)) throw Error("vk_invalid_upload_host");
  const transport = env.VK_UPLOAD_TRANSPORT === "fixed" ? "fixed" : "formdata";
  const response = await postVkMultipart(url, photo, job.asset_key + ".jpg", transport);
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
  // Не публикуем устаревшее тестовое сообщение даже при позднем включении Cron.
  if (job.state === "queued" && String(job.operation_id).startsWith("test:")) {
    const when = Date.parse(String(job.created_at).replace(" ", "T") + "Z");
    if (!Number.isFinite(when) || Date.now() - when > 10 * 60_000) {
      await markState(db, job, "queued", "superseded", { diagnostic: "test_expired" });
      return "done";
    }
  }
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
        await markState(db, job, "preparing", "ready", {
          upload_result: uploadResult, verification_attempts: 0, diagnostic: null
        });
      }
    } catch (err) {
      // Безопасный повтор ТОЛЬКО ДО stories.save. Ошибка ответа загрузочного
      // сервера ещё не означает публикацию истории.
      const reason = String(err?.message || err).slice(0, 90);
      const temporaryVkUpload = job.platform === "vk" &&
        /^(vk_upload_code_1|vk_upload_invalid_json|vk_upload_code_(429|500|502|503|504))$/.test(reason);
      const attempts = Number(job.verification_attempts || 0) + 1;
      if (temporaryVkUpload && attempts < 3) {
        await markState(db, job, "preparing", "queued", {
          verification_attempts: attempts,
          diagnostic: "vk_upload_retry_" + attempts + "_" + reason
        });
        // Следующую попытку делает Cron, с НОВЫМ upload URL, не в этом запросе.
        return "wait";
      }
      // После исчерпания попыток либо другой ошибки — только ручная проверка.
      await markState(db, job, "preparing", "review_required", { diagnostic: reason });
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


async function mediaPreflight(env) {
  if (!env.DB) return "❌ D1 не подключена";
  const settings = await env.DB.prepare(
    "SELECT enabled FROM light_publish_settings WHERE id = 1"
  ).first();
  const jobs = await env.DB.prepare(
    "SELECT COUNT(*) AS n FROM light_publication_jobs"
  ).first();
  const checked = await Promise.all(
    [...LIGHT_ASSET_KEYS].flatMap(key => ["jpg", "png"].map(async ext => {
      const url = LIGHT_ASSETS_ORIGIN + "/media/light/" + key + "." + ext;
      try {
        const response = await fetch(url, {
          method: "HEAD", signal: AbortSignal.timeout(9000),
        });
        const type = (response.headers.get("content-type") || "").toLowerCase();
        const expected = ext === "jpg" ? "image/jpeg" : "image/png";
        return { key: key + "." + ext, ok: response.ok && type.includes(expected) };
      } catch {
        return { key: key + "." + ext, ok: false };
      }
    }))
  );
  const failed = checked.filter(x => !x.ok);
  const lines = [
    "🔎 ЛИНИЯ СПОРТА · ПРОВЕРКА ГОТОВНОСТИ",
    "",
    "Хранилище Cloudflare Pages: " + (16 - failed.length) + "/16 файлов доступны",
    "D1: таблицы очереди доступны",
    "Заданий в очереди: " + Number(jobs?.n || 0),
    "Настройка публикации в D1: " +
      (Number(settings?.enabled) === 1 ? "ВКЛЮЧЕНА" : "ВЫКЛЮЧЕНА"),
    "Общий статус публикации: " +
      (await publishingEnabled(env) ? "ВКЛЮЧЕНА" : "ВЫКЛЮЧЕНА"),
  ];
  if (failed.length) {
    lines.push("", "Недоступные файлы:");
    lines.push(...failed.slice(0, 16).map(x => "• " + x.key));
  }
  lines.push("", "🧪 Только чтение: никаких сторис не отправлено.");
  return lines.join("\n");
}

// Cron помечает зависшие промежуточные шаги для ручной проверки.
// НИКОГДА не повторяет потенциально уже выполненный вызов publish/save.
async function markAbandonedJobs(db, mode = "live") {
  const filter = mode === "test" ? "LIKE" : "NOT LIKE";
  await db.prepare(
    "UPDATE light_publication_jobs SET state = 'review_required', " +
    "diagnostic = 'interrupted_before_or_during_external_publish', " +
    "updated_at = CURRENT_TIMESTAMP " +
    "WHERE state IN ('preparing','publishing') " +
    "AND operation_id " + filter + " 'test:%' " +
    "AND datetime(updated_at) < datetime('now', '-3 minutes')"
  ).run();
  // Meta иногда продолжает обработку контейнера слишком долго.
  // Через 20 минут требуем ручную проверку без повторной отправки.
  await db.prepare(
    "UPDATE light_publication_jobs SET state = 'review_required', " +
    "diagnostic = 'media_processing_timeout', updated_at = CURRENT_TIMESTAMP " +
    "WHERE state = 'processing' AND operation_id " + filter + " 'test:%' " +
    "AND datetime(updated_at) < datetime('now', '-20 minutes')"
  ).run();
}


// --- Изолированный контролируемый тест для владельца. Администраторы не затронуты. ---
// Работает ТОЛЬКО при TEST_PUBLISH_ENABLED=true, PUBLISH_ENABLED!=true
// и light_publish_settings.enabled=0. Во всех иных режимах не публикует.
async function testModeEnabled(env) {
  if (String(env.TEST_PUBLISH_ENABLED || "").toLowerCase() !== "true") return false;
  if (String(env.PUBLISH_ENABLED || "").toLowerCase() === "true") return false;
  const settings = await env.DB.prepare(
    "SELECT enabled FROM light_publish_settings WHERE id = 1"
  ).first();
  return Number(settings?.enabled) === 0;
}

function testMenuView(clubs) {
  const rows = clubs.filter(c => ["on", "off"].includes(c.status));
  return {
    text: [
      "🧪 ЛИНИЯ СПОРТА · КОНТРОЛЬНАЯ ПУБЛИКАЦИЯ",
      "",
      "Проверяется реальная публикация в Instagram и VK.",
      "История будет видна подписчикам. Выбери клуб только после",
      "проверки фактического состояния света в нём.",
      "",
      ...clubs.map(c => statusLabel(c.status) + " — " + c.name),
      "",
      "Выбор клуба открывает отдельное подтверждение.",
      "Статусы клубов в D1 не меняются.",
    ].join("\n"),
    keyboard: [
      ...rows.map(c => [{ text: c.name, callback_data: "testselect:" + c.id }]),
      [{ text: "Отмена", callback_data: "menu" }],
    ],
  };
}

function testConfirmView(club) {
  return {
    text: [
      "⚠️ РЕАЛЬНАЯ ТЕСТОВАЯ ПУБЛИКАЦИЯ",
      "",
      club.name,
      "Свет: " + statusLabel(club.status),
      "",
      "После подтверждения будет отправлена ОДНА история",
      "в Instagram и ОДНА история во ВКонтакте.",
      "Их увидят реальные подписчики.",
      "",
      "Подтверждай, только если указанный статус верен.",
      "Это не имитация и не приватный черновик.",
    ].join("\n"),
    keyboard: [
      [{ text: "✅ Опубликовать в обеих сетях", callback_data: "testsend:" + club.id + ":" + club.status }],
      [{ text: "Отмена", callback_data: "menu" }],
    ],
  };
}

async function createOwnerTestJobs(env, user, club) {
  // Постоянный ключ на клуб+статус: случайное повторное нажатие или
  // повторная доставка webhook не смогут запустить повторную публикацию.
  const operationId = "test:" + club.id + ":" + club.status;
  const key = club.id + "-" + club.status;
  const statements = [
    env.DB.prepare(
      "INSERT OR IGNORE INTO light_operations " +
      "(operation_id,telegram_id,scope,club_id,new_status,processed,changed_count) " +
      "VALUES (?,?,'club',?,?,1,0)"
    ).bind(operationId, user.telegram_id, club.id, club.status),
    ...["instagram", "vk"].map(platform => env.DB.prepare(
      "INSERT OR IGNORE INTO light_publication_jobs " +
      "(job_id,operation_id,scope,club_id,new_status,platform,asset_key,state) " +
      "VALUES (?,?,'club',?,?,?,?,'queued')"
    ).bind(operationId + ":" + platform, operationId, club.id, club.status, platform, key))
  ];
  await env.DB.batch(statements);
  return (await env.DB.prepare(
    "SELECT platform, state, external_id FROM light_publication_jobs " +
    "WHERE operation_id = ? ORDER BY platform"
  ).bind(operationId).all()).results;
}

async function ownerTestStatus(env) {
  const items = (await env.DB.prepare(
    "SELECT job_id,platform,state,external_id,updated_at FROM light_publication_jobs " +
    "WHERE operation_id LIKE 'test:%' ORDER BY created_at DESC, platform LIMIT 12"
  ).all()).results;
  if (!items.length) return "🧪 Тестовых публикаций ещё нет.";
  const lines = ["🔎 ЛИНИЯ СПОРТА · ТЕСТОВЫЕ ПУБЛИКАЦИИ", ""];
  for (const job of items) {
    const icon = job.state === "published" ? "✅" :
      job.state === "review_required" || job.state === "failed" ? "⚠️" : "⏳";
    lines.push(icon + " " + job.platform.toUpperCase() + " · " +
      job.job_id.split(":").slice(1, 3).join("/") + " · " + job.state);
    if (job.external_id) lines.push("ID истории: " + job.external_id);
  }
  lines.push("", "⚠️ review_required — проверить соцсеть вручную, повтор не запускать.");
  return lines.join("\n");
}

async function onOwnerTestCallback(callback, env, user, data) {
  if (user.role !== "owner") return answer(env, callback.id, "Нет доступа", true);
  if (!await testModeEnabled(env)) {
    return answer(env, callback.id, "Контрольный режим отключён", true);
  }
  const parts = data.split(":");
  const action = parts[0], clubId = parts[1];
  if (!CLUB_IDS.includes(clubId)) {
    return answer(env, callback.id, "Неверный клуб", true);
  }
  const club = await allowedClub(env.DB, user, clubId);
  if (!club || !["on","off"].includes(club.status)) {
    return answer(env, callback.id, "Статус неизвестен", true);
  }
  const chatId = callback.message.chat.id;
  const messageId = callback.message.message_id;
  if (action === "testselect" && parts.length === 2) {
    await answer(env, callback.id);
    return render(env, chatId, messageId, testConfirmView(club));
  }
  if (action !== "testsend" || parts.length !== 3 || parts[2] !== club.status) {
    return answer(env, callback.id, "Статус изменился. Начните заново: /testpost", true);
  }
  const jobs = await createOwnerTestJobs(env, user, club);
  await answer(env, callback.id, "Проверка поставлена в очередь");
  return render(env, chatId, messageId, {
    text: [
      "🧪 КОНТРОЛЬНАЯ ПУБЛИКАЦИЯ",
      "",
      club.name + " · " + statusLabel(club.status),
      "",
      ...jobs.map(j => j.platform.toUpperCase() + ": " + j.state),
      "",
      "Следи за результатом командой /teststatus.",
      "В случае ошибки не повторяй публикацию до проверки соцсети.",
      "Режим администраторов не изменён.",
    ].join("\n"),
    keyboard: [[{text: "⬅️ К списку клубов", callback_data: "menu"}]],
  });
}

async function queueWork(env, maxMs = 17000) {
  const live = await publishingEnabled(env);
  const test = !live && await testModeEnabled(env);
  if (!live && !test) return;
  await markAbandonedJobs(env.DB, test ? "test" : "live");
  const start = Date.now();
  const paused = new Set();
  for (let i = 0; i < 12 && Date.now() - start < maxMs; i++) {
    const filter = test ? "LIKE" : "NOT LIKE";
    const pending = (await env.DB.prepare(`SELECT * FROM light_publication_jobs
      WHERE state IN ('queued','processing','ready','submitted')
      AND operation_id ${filter} 'test:%'
      ORDER BY created_at, job_id LIMIT 30`).all()).results;
    const job = pending.find(item => !paused.has(item.job_id));
    if (!job) return;
    const outcome = await advanceJob(env, job);
    // Пока Meta обрабатывает контейнер, не блокировать VK и другие задания.
    if (outcome === "wait") paused.add(job.job_id);
  }
}


// --- Уведомления о подтверждённых публикациях: один итог на событие ---
// Операции до установки SQL-миграции не рассылаются задним числом.
// Каждому получателю одно сообщение: инициатор + действующие владельцы.
// При неопределённой доставке не отправляем второй раз автоматически.
const LIGHT_CLUB_LABELS = Object.freeze({
  heroes6d: "Героев Сталинграда, 6Д",
  konnaya25: "1-й Конной Армии, 25А",
  kuib60: "Куйбышева, 60",
});
const LIGHT_FINAL_STATES = new Set([
  "published", "failed", "review_required", "superseded"
]);

function moscowConfirmedAt(utcString) {
  if (!utcString) return "неизвестно";
  const utc = String(utcString).replace(" ", "T").replace(/Z?$/, "Z");
  const time = new Date(utc);
  if (Number.isNaN(time.valueOf())) return "неизвестно";
  return new Intl.DateTimeFormat("ru-RU", {
    timeZone: "Europe/Moscow",
    year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit",
    hour12: false
  }).format(time) + " МСК";
}

function lightNoticeText(op, jobs) {
  const byPlatform = Object.fromEntries(jobs.map(j => [j.platform, j]));
  const bothPublished = jobs.every(j => j.state === "published");
  const allSuperseded = jobs.every(j => j.state === "superseded");
  const place = op.scope === "all" ? "Все три клуба" :
    (LIGHT_CLUB_LABELS[op.club_id] || op.club_id);
  const state = statusLabel(op.new_status);
  const show = platform => {
    const j = byPlatform[platform];
    const label = platform === "instagram" ? "Instagram" : "ВКонтакте";
    if (!j) return "⚠️ " + label + ": нет записи";
    if (j.state === "published") {
      return "✅ " + label + ": опубликовано\n" +
        "    Подтверждено: " + moscowConfirmedAt(j.updated_at);
    }
    if (j.state === "superseded") return "↪️ " + label + ": отменено более новым статусом";
    return "⚠️ " + label + ": требуется проверка (" + j.state + ")";
  };
  return [
    bothPublished ? "✅ СТОРИС ОПУБЛИКОВАНЫ" :
      allSuperseded ? "↪️ СТОРИС НЕ ОТПРАВЛЕНЫ: СТАТУС УЖЕ ОБНОВИЛСЯ" :
      "⚠️ ПУБЛИКАЦИЯ ТРЕБУЕТ ВНИМАНИЯ",
    "🏋️ ЛИНИЯ СПОРТА · СВЕТ",
    "",
    "📍 " + place,
    "Состояние: " + state,
    "",
    show("instagram"),
    show("vk"),
    "",
    "Время указано по Москве, по подтверждению системой.",
    bothPublished || allSuperseded ? "" :
      "Не повторяйте отправку до проверки истории в соцсетях."
  ].filter(Boolean).join("\n");
}

async function notifyPublicationResults(env) {
  if (!env.TELEGRAM_BOT_TOKEN || !env.DB) return;
  const settings = await env.DB.prepare(
    "SELECT started_at FROM light_notice_config WHERE id = 1"
  ).first();
  if (!settings?.started_at) return;
  const ops = (await env.DB.prepare(
    "SELECT o.operation_id, o.scope, o.club_id, o.new_status, o.telegram_id " +
    "FROM light_operations o JOIN light_publication_jobs j " +
    "ON j.operation_id = o.operation_id " +
    "WHERE o.operation_id NOT LIKE 'test:%' AND j.created_at >= ? " +
    "AND (NOT EXISTS (SELECT 1 FROM light_notification_receipts n " +
    "WHERE n.operation_id = o.operation_id AND n.telegram_id = o.telegram_id) " +
    "OR EXISTS (SELECT 1 FROM admins a WHERE a.role = 'owner' " +
    "AND a.active = 1 AND NOT EXISTS " +
    "(SELECT 1 FROM light_notification_receipts n " +
    "WHERE n.operation_id = o.operation_id AND n.telegram_id = a.telegram_id))) " +
    "GROUP BY o.operation_id " +
    "HAVING COUNT(*) = 2 AND SUM(CASE WHEN j.state IN " +
    "('published','failed','review_required','superseded') " +
    "THEN 1 ELSE 0 END) = 2 " +
    "ORDER BY MAX(j.updated_at) DESC LIMIT 40"
  ).bind(settings.started_at).all()).results;

  if (!ops.length) return;
  const owners = (await env.DB.prepare(
    "SELECT telegram_id FROM admins WHERE role = 'owner' AND active = 1"
  ).all()).results;
  for (const op of ops) {
    const jobs = (await env.DB.prepare(
      "SELECT platform, state, updated_at FROM light_publication_jobs " +
      "WHERE operation_id = ? ORDER BY platform"
    ).bind(op.operation_id).all()).results;
    if (jobs.length !== 2 ||
        jobs.some(j => !LIGHT_FINAL_STATES.has(j.state))) continue;
    const recipients = new Set([
      String(op.telegram_id), ...owners.map(o => String(o.telegram_id))
    ]);
    const msg = lightNoticeText(op, jobs);
    for (const recipient of recipients) {
      const chatId = Number(recipient);
      if (!Number.isSafeInteger(chatId) || chatId <= 0) continue;
      await env.DB.prepare(
        "INSERT OR IGNORE INTO light_notification_receipts " +
        "(operation_id, telegram_id, state) VALUES (?, ?, 'pending')"
      ).bind(op.operation_id, chatId).run();
      const locked = await env.DB.prepare(
        "UPDATE light_notification_receipts SET state = 'sending' " +
        "WHERE operation_id = ? AND telegram_id = ? AND state = 'pending'"
      ).bind(op.operation_id, chatId).run();
      if (Number(locked.meta?.changes || 0) !== 1) continue;
      try {
        const sent = await tg(env, "sendMessage", {
          chat_id: chatId,
          text: msg,
          disable_web_page_preview: true,
        });
        await env.DB.prepare(
          "UPDATE light_notification_receipts " +
          "SET state = 'sent', sent_at = CURRENT_TIMESTAMP, message_id = ? " +
          "WHERE operation_id = ? AND telegram_id = ? AND state = 'sending'"
        ).bind(sent.message_id || null, op.operation_id, chatId).run();
      } catch (error) {
        // Сетевые сбои доставки в Telegram могут быть неоднозначны.
        // Второй раз без проверки не отправляем, чтобы не спамить.
        await env.DB.prepare(
          "UPDATE light_notification_receipts " +
          "SET state = 'review_required', diagnostic = ? " +
          "WHERE operation_id = ? AND telegram_id = ? AND state = 'sending'"
        ).bind("telegram_delivery_uncertain", op.operation_id, chatId).run();
        console.warn("Light notice: delivery needs review");
      }
    }
  }
}

async function lightHistoryText(env) {
  const ops = (await env.DB.prepare(
    "SELECT o.operation_id, o.scope, o.club_id, o.new_status " +
    "FROM light_operations o " +
    "WHERE o.operation_id NOT LIKE 'test:%' AND " +
    "EXISTS (SELECT 1 FROM light_publication_jobs j " +
    "WHERE j.operation_id = o.operation_id) " +
    "ORDER BY o.rowid DESC LIMIT 8"
  ).all()).results;
  if (!ops.length) return "📚 Публикаций пока нет.";
  const lines = ["📚 ЛИНИЯ СПОРТА · ИСТОРИЯ СТОРИС", ""];
  for (const op of ops) {
    const jobs = (await env.DB.prepare(
      "SELECT platform, state, updated_at FROM light_publication_jobs " +
      "WHERE operation_id = ? ORDER BY platform"
    ).bind(op.operation_id).all()).results;
    const place = op.scope === "all" ? "Все три клуба" :
      (LIGHT_CLUB_LABELS[op.club_id] || op.club_id);
    lines.push("📍 " + place + " · " + statusLabel(op.new_status));
    for (const p of ["instagram", "vk"]) {
      const j = jobs.find(x => x.platform === p);
      if (j) lines.push(
        (j.state === "published" ? "✅ " : "⚠️ ") +
        (p === "vk" ? "VK" : "IG") + ": " + j.state +
        " · " + moscowConfirmedAt(j.updated_at)
      );
    }
    lines.push("");
  }
  lines.push("Указано время подтверждения в Cloudflare, МСК.");
  return lines.join("\n");
}

async function queueCycleWithNotifications(env, maxMs) {
  try { await queueWork(env, maxMs); }
  catch (error) { console.error("Light queue:", String(error?.message || error).slice(0, 95)); }
  try { await notifyPublicationResults(env); }
  catch (error) { console.error("Light notices:", String(error?.message || error).slice(0, 95)); }
}


// Диагностика ВКонтакте только для владельца: загружает JPEG во временное
// хранилище VK, но НИКОГДА не вызывает stories.save и ничего не публикует.
// Не сохраняем upload_url, upload_result, токен, параметры запроса и тело ответа.
async function vkUploadProbe(env, transport = "formdata") {
  const started = Date.now();
  let stage = "account";
  let uploadHost = "unknown";
  let httpStatus = null;
  let contentType = "unknown";
  let bodyLength = 0;
  let errorCode = null;
  let outcome = "unknown";
  let fileType = "image/jpeg";

  try {
    await verifyVkTarget(env);
    stage = "asset";
    const photo = await fetchImage(LIGHT_ASSETS_ORIGIN +
      "/media/light/heroes6d-on.jpg", "jpg");
    stage = "upload_server";
    const uploadServer = await vkApi(env, "stories.getPhotoUploadServer", {
      group_id: EXPECTED_VK_ID, add_to_news: "1",
    });
    if (!isValidHTTPS(uploadServer?.upload_url)) {
      throw Error("vk_probe_no_https_upload_server");
    }
    const uploadUrl = new URL(uploadServer.upload_url);
    uploadHost = uploadUrl.hostname.toLowerCase();
    if (!/(^|\.)vk\.(ru|com)$/.test(uploadHost)) {
      throw Error("vk_probe_unexpected_upload_host");
    }
    stage = "upload";
    const response = await postVkMultipart(
      uploadUrl, photo, "heroes6d-on.jpg", transport
    );
    httpStatus = response.status;
    contentType = String(response.headers.get("content-type") || "unknown")
      .split(";")[0].slice(0, 45);
    const raw = await response.text();
    bodyLength = raw.length;
    let data = null;
    try { data = JSON.parse(raw); } catch { /* No body content is logged. */ }
    if (!data) {
      outcome = "invalid_json";
    } else if (!response.ok || data.error) {
      errorCode = Number(data.error?.error_code || data.error?.code || response.status);
      outcome = "server_error";
    } else {
      const uploadResult = data.response?.upload_result ??
        data.response?.upload_results ?? data.upload_result ?? data.upload_results;
      const value = Array.isArray(uploadResult) ? uploadResult[0] : uploadResult;
      outcome = typeof value === "string" && value.length > 0
        ? "uploaded_to_temporary_storage" : "missing_upload_result";
    }
  } catch (e) {
    const message = String(e?.message || "");
    const safe = /^vk_[a-z0-9_]+$/.test(message) ? message :
      e?.name === "TimeoutError" || e?.name === "AbortError" ? "request_timeout" :
      "network_or_runtime_error";
    outcome = safe;
  }
  const passed = outcome === "uploaded_to_temporary_storage";
  const lines = [
    (passed ? "✅" : "❌") + " VK · ПРОБНАЯ ЗАГРУЗКА JPEG",
    "Транспорт: " + transport,
    "Результат: " + outcome,
    "Этап: " + stage,
    "Сервер: " + uploadHost,
    "HTTP: " + (httpStatus === null ? "не получен" : httpStatus),
    "Тип ответа: " + contentType,
    "Размер ответа: " + bodyLength + " символов",
    "Код ответа VK: " + (errorCode === null ? "—" : errorCode),
    "Время запроса: " + (Date.now() - started) + " мс",
    "",
    "🔒 История НЕ создавалась: stories.save не вызывался.",
    "Токены и адрес загрузки не выводятся."
  ];
  return lines.join("\n");
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
  if (command === "/vkprobe" || command === "/vkfixed") {
    if (user.role !== "owner") {
      await tg(env, "sendMessage", {
        chat_id: msg.chat.id, text: "⛔ Команда доступна только владельцу.",
      });
      return;
    }
    await tg(env, "sendMessage", {
      chat_id: msg.chat.id, text: await vkUploadProbe(env, command === "/vkfixed" ? "fixed" : "formdata"),
    });
    return;
  }
  if (command === "/history") {
    if (user.role !== "owner") {
      await tg(env, "sendMessage", {
        chat_id: msg.chat.id, text: "⛔ История доступна только владельцу.",
      });
      return;
    }
    await tg(env, "sendMessage", {
      chat_id: msg.chat.id, text: await lightHistoryText(env),
    });
    return;
  }
  if (command === "/testpost" || command === "/teststatus") {
    if (user.role !== "owner") {
      await tg(env, "sendMessage", {
        chat_id: msg.chat.id, text: "⛔ Команда доступна только владельцу.",
      });
      return;
    }
    if (command === "/teststatus") {
      await tg(env, "sendMessage", {
        chat_id: msg.chat.id, text: await ownerTestStatus(env),
      });
      return;
    }
    if (!await testModeEnabled(env)) {
      await tg(env, "sendMessage", {
        chat_id: msg.chat.id,
        text: "🧪 Режим теста выключен. Пока публикация невозможна.\n" +
          "Для теста требуется TEST_PUBLISH_ENABLED=true при двух выключенных боевых флагах.",
      });
      return;
    }
    await render(env, msg.chat.id, null,
      testMenuView(await getVisible(env.DB, user)));
    return;
  }
  if (command === "/preflight") {
    if (user.role !== "owner") {
      await tg(env, "sendMessage", {
        chat_id: msg.chat.id, text: "⛔ Команда доступна только владельцу.",
      });
      return;
    }
    await tg(env, "sendMessage", {
      chat_id: msg.chat.id,
      text: await mediaPreflight(env),
    });
    return;
  }
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


// Предупреждение о повторе: без новых сообщений и без вызовов Meta/VK.
// Telegram answerCallbackQuery поддерживает максимум 200 символов.
async function duplicateStoryWarning(db, scope, clubId, state) {
  const title = scope === "all" ? "Все три клуба" :
    (LIGHT_CLUB_LABELS[clubId] || clubId);
  const assetKey = (scope === "all" ? "all" : clubId) + "-" + state;
  const recent = (await db.prepare(
    "SELECT platform, state, updated_at FROM light_publication_jobs " +
    "WHERE asset_key = ? ORDER BY created_at DESC, job_id DESC LIMIT 30"
  ).bind(assetKey).all()).results || [];
  const latest = {};
  for (const j of recent) {
    if (!latest[j.platform]) latest[j.platform] = j;
  }
  function channel(name, platform) {
    const item = latest[platform];
    if (!item) return name + ": нет записи";
    if (item.state === "published") {
      const date = moscowConfirmedAt(item.updated_at).replace(", ", " ");
      return name + ": опубликовано " + date;
    }
    if (["queued", "preparing", "processing", "ready", "publishing", "submitted"].includes(item.state)) {
      return name + ": обработка ещё идёт";
    }
    return name + ": публикация не подтверждена";
  }
  const message = [
    "⚠️ " + title + " — статус «" + (state === "on" ? "Свет есть" : "Света нет") + "» уже установлен.",
    "Повторная сторис не отправлена.",
    channel("IG", "instagram"),
    channel("VK", "vk")
  ].join("\n");
  return message.slice(0, 200);
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

  if (data.startsWith("testselect:") || data.startsWith("testsend:")) {
    return onOwnerTestCallback(callback, env, user, data);
  }
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
    if (!changed) {
      await answer(env, callback.id,
        await duplicateStoryWarning(env.DB, "all", null, state), true);
    } else {
      await answer(env, callback.id, `Обновлено клубов: ${changed} из 3`);
    }
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
  if (!changed) {
    await answer(env, callback.id,
      await duplicateStoryWarning(env.DB, "club", clubId, state), true);
  } else {
    await answer(env, callback.id, "Состояние сохранено");
  }
  const updated = await allowedClub(env.DB, user, clubId);
  return render(env, chatId, messageId, clubView(updated, await publishingEnabled(env)));
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    if (request.method === "GET" && url.pathname === "/") {
      return json({ status: "ok", service: "ls-light-bot", version: "4.6", publishingEnabled: await publishingEnabled(env), testModeEnabled: await testModeEnabled(env) });
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
        ctx.waitUntil(queueCycleWithNotifications(env, 17000));
      }
      return json({ ok: true });
    } catch (e) {
      console.error("Ошибка Telegram / D1:", e.message);
      return json({ error: "temporary_failure" }, 500);
    }
  },
  async scheduled(_controller, env, ctx) {
    ctx.waitUntil(queueCycleWithNotifications(env, 22000));
  },
};