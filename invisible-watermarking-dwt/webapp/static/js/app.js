/* Lab Watermark DWT — dashboard (vanilla JS, tanpa build step) */
(() => {
'use strict';

/* ================= util ================= */
const $ = (s, r = document) => r.querySelector(s);
const clamp = (v, a = 0, b = 1) => Math.min(b, Math.max(a, v));

function h(tag, attrs, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v == null || v === false) continue;
    if (k === 'class') el.className = v;
    else if (k === 'html') el.innerHTML = v;            // hanya string statis tepercaya (ikon)
    else if (k.startsWith('on')) el.addEventListener(k.slice(2), v);
    else el.setAttribute(k, v === true ? '' : v);
  }
  for (const kid of kids.flat(Infinity)) {
    if (kid == null || kid === false) continue;
    el.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
  }
  return el;
}

const SID_RE = /^[A-Za-z0-9_-]{8,64}$/;
const newSid = () => (crypto.randomUUID ? crypto.randomUUID().replace(/-/g, '')
  : (Math.random().toString(16).slice(2) + Date.now().toString(16)).padEnd(16, '0'));
let SID = null;
try { SID = localStorage.getItem('wm_sid'); } catch { /* mode privat */ }
if (!SID || !SID_RE.test(SID)) { SID = newSid(); try { localStorage.setItem('wm_sid', SID); } catch {} }

const state = { options: null, pending: null };

async function api(path, { method = 'GET', json, form } = {}) {
  const opt = { method, headers: { 'X-Session-Id': SID } };
  if (json) { opt.headers['Content-Type'] = 'application/json'; opt.body = JSON.stringify(json); }
  if (form) opt.body = form;
  let res;
  try { res = await fetch('/api' + path, opt); }
  catch { throw new Error('Server tidak dapat dihubungi. Pastikan aplikasi masih berjalan.'); }
  let data = null;
  try { data = await res.json(); } catch {}
  if (!res.ok) throw new Error((data && data.error) || `Permintaan gagal (${res.status}).`);
  return data;
}

function toast(msg, err = false) {
  const t = h('div', { class: 'toast' + (err ? ' err' : '') }, msg);
  $('#toasts').append(t);
  setTimeout(() => t.remove(), err ? 7000 : 3500);
}

async function withBusy(btn, label, fn) {
  const orig = [...btn.childNodes];
  btn.disabled = true;
  btn.replaceChildren(h('span', { class: 'spinner' }), label);
  try { return await fn(); }
  finally { btn.disabled = false; btn.replaceChildren(...orig); }
}

const KIND = { embed: 'Penyisipan', extract: 'Ekstraksi', attack: 'Serangan' };
const WM_TYPE = { image: 'Logo gambar', text: 'Teks', binary: 'Biner' };
const fmtDate = ts => new Date(ts * 1000).toLocaleString('id-ID', { dateStyle: 'medium', timeStyle: 'short' });
const wvLabel = w => ({ haar: 'Haar', db1: 'Db1 (setara Haar)', db4: 'Db4' }[w] || w);
const go = key => { location.hash = '#/' + key; };
const takeNote = (pend, key) => (pend && pend[key]) || null;

/* ================= komponen dasar ================= */
const card = (...kids) => h('section', { class: 'card' }, ...kids);
const pageHead = (title, text) => h('div', { class: 'page-head' }, h('h1', {}, title), text && h('p', {}, text));
const linkBtn = (label, key, ghost = false) => h('a', { class: 'btn' + (ghost ? ' ghost' : ''), href: '#/' + key }, label);

function emptyState(title, text, ...actions) {
  return h('div', { class: 'empty' }, h('strong', {}, title), text && h('span', {}, text), actions.length ? h('div', { class: 'row' }, ...actions) : null);
}

function field(label, control, hint) {
  const wrap = ['INPUT', 'SELECT', 'TEXTAREA'].includes(control.tagName) ? 'label' : 'div';
  return h(wrap, { class: 'field' }, h('span', { class: 'lbl' }, label), control, hint && h('p', { class: 'hint' }, hint));
}

function segmented(options, value, onChange) {
  const el = h('div', { class: 'seg', role: 'group' });
  let cur = value;
  const btns = options.map(o => h('button', { type: 'button', 'data-v': String(o.value), onclick: () => set(o.value, true) }, o.label));
  function set(v, emit) {
    cur = v;
    btns.forEach(b => b.setAttribute('aria-pressed', String(b.dataset.v === String(v))));
    if (emit && onChange) onChange(v);
  }
  el.append(...btns);
  set(value, false);
  return { el, get: () => cur, set: v => set(v, false) };
}

function rangeField({ label, min, max, step, value, fmt = v => v, hint, onInput }) {
  const out = h('output', {}, fmt(value));
  const input = h('input', { type: 'range', min, max, step, value });
  input.addEventListener('input', () => { out.textContent = fmt(+input.value); if (onInput) onInput(+input.value); });
  const el = h('div', { class: 'field' }, h('div', { class: 'field-head' }, h('span', { class: 'lbl' }, label), out), input, hint && h('p', { class: 'hint' }, hint));
  return { el, get: () => +input.value, set: v => { input.value = v; out.textContent = fmt(+v); } };
}

function dropzone({ label, hint, compact = false, onClear } = {}) {
  let file = null, url = null;
  const input = h('input', { type: 'file', accept: 'image/png,image/jpeg,image/webp,image/bmp', class: 'sr-only' });
  const img = h('img', { class: 'dz-preview', alt: 'Pratinjau citra terpilih', hidden: true });
  const msg = h('div', { class: 'dz-msg' }, h('strong', {}, label), hint && h('span', {}, hint));
  const clear = h('button', { class: 'btn ghost sm dz-clear', type: 'button', hidden: true,
    onclick: e => { e.preventDefault(); e.stopPropagation(); reset(); if (onClear) onClear(); } }, 'Hapus');
  const el = h('label', { class: 'dropzone' + (compact ? ' compact' : '') }, input, img, msg, clear);

  function show(src) { img.src = src; img.hidden = false; msg.hidden = true; clear.hidden = false; }
  function reset() {
    if (url) URL.revokeObjectURL(url);
    url = null; file = null; input.value = '';
    img.hidden = true; img.removeAttribute('src'); msg.hidden = false; clear.hidden = true;
  }
  function set(f) {
    if (!f) return;
    if (!f.type.startsWith('image/')) { toast('Berkas harus berupa citra (PNG atau JPG).', true); return; }
    if (url) URL.revokeObjectURL(url);
    file = f; url = URL.createObjectURL(f); show(url);
  }
  input.addEventListener('change', () => set(input.files[0]));
  el.addEventListener('dragover', e => { e.preventDefault(); el.classList.add('over'); });
  el.addEventListener('dragleave', () => el.classList.remove('over'));
  el.addEventListener('drop', e => { e.preventDefault(); el.classList.remove('over'); set(e.dataTransfer.files[0]); });
  return { el, get file() { return file; }, setUrl(u) { reset(); show(u); }, reset };
}

function paramsPanel() {
  const o = state.options;
  const wavelet = h('select', {}, o.wavelets.map(w => h('option', { value: w }, wvLabel(w))),
    !o.wavelets.includes('db4') && h('option', { value: 'db4', disabled: true }, 'Db4 (butuh PyWavelets)'));
  const level = segmented([{ value: 1, label: 'Level 1' }, { value: 2, label: 'Level 2' }], 2);
  const alpha = rangeField({ label: 'Alpha (Δ) — kekuatan penyisipan', min: o.delta.min, max: o.delta.max, step: 1, value: o.delta.default,
    fmt: v => `Δ ${v}`, hint: 'Makin besar: lebih tahan serangan, tetapi kualitas visual turun.' });
  const key = h('input', { type: 'number', min: 0, max: 2147483647, value: 2024 });
  const el = h('div', {},
    field('Jenis wavelet', wavelet),
    field('Level dekomposisi', level.el, 'Level 2 lebih tahan kompresi; level 1 menyisipkan di detail lebih halus.'),
    alpha.el,
    field('Kunci rahasia', key, 'Menentukan posisi penyisipan. Harus sama saat ekstraksi.'));
  return {
    el,
    append(fd) { fd.append('wavelet', wavelet.value); fd.append('level', level.get()); fd.append('delta', alpha.get()); fd.append('key', key.value || '2024'); },
    set(cfg) { if (o.wavelets.includes(cfg.wavelet)) wavelet.value = cfg.wavelet; level.set(cfg.level); alpha.set(cfg.delta); key.value = cfg.key; },
  };
}

function wmInput(mode) {
  const emb = mode === 'embed', o = state.options;
  const prefix = emb ? 'wm_' : 'exp_';
  const type = segmented(Object.entries(WM_TYPE).map(([value, label]) => ({ value, label })), 'image', v => show(v));
  const size = h('select', {}, o.wm_sizes.map(s => h('option', { value: s, selected: s === 32 }, `${s} × ${s} piksel (${s * s} bit)`)));
  const logo = dropzone({ label: emb ? 'Unggah logo (opsional)' : 'Watermark asli (opsional)',
    hint: emb ? 'Kosong = logo bawaan “DWT”. Dibinarkan otomatis.' : 'Dipakai untuk menghitung BER.', compact: true });
  const text = h('input', { type: 'text', placeholder: 'mis. © Budi Santoso 2026', autocomplete: 'off' });
  const count = h('p', { class: 'hint' }, `0 / ${o.text_bytes} byte`);
  text.addEventListener('input', () => {
    const n = new TextEncoder().encode(text.value).length;
    count.textContent = `${n} / ${o.text_bytes} byte`;
    count.style.color = n > o.text_bytes ? 'var(--bad)' : '';
  });
  const bin = h('textarea', { placeholder: 'mis. 1011001110001111', spellcheck: 'false' });
  const binCount = h('p', { class: 'hint' }, `0 bit (${o.binary_bits[0]}–${o.binary_bits[1]})`);
  bin.addEventListener('input', () => {
    bin.value = bin.value.replace(/[^01\s]/g, '');
    binCount.textContent = `${bin.value.replace(/\s/g, '').length} bit (${o.binary_bits[0]}–${o.binary_bits[1]})`;
  });
  const nbits = h('input', { type: 'number', min: o.binary_bits[0], max: o.binary_bits[1], value: 64 });
  const panels = {
    image: h('div', {}, field('Ukuran watermark', size), h('div', { style: 'margin-top:12px' }, logo.el)),
    text: h('div', {}, field(emb ? 'Teks watermark' : 'Teks watermark asli (opsional)', text), count),
    binary: h('div', {}, field(emb ? 'Bit watermark (0/1)' : 'Bit watermark asli (opsional)', bin), binCount,
      !emb && h('div', { style: 'margin-top:12px' }, field('Jumlah bit', nbits, 'Isi bila bit asli tidak dimasukkan.'))),
  };
  function show(v) { Object.entries(panels).forEach(([k, p]) => { p.hidden = k !== v; }); }
  show('image');
  return {
    el: h('div', {}, field('Jenis watermark', type.el), h('div', { style: 'margin-top:14px' }, panels.image, panels.text, panels.binary)),
    append(fd) {
      const t = type.get();
      fd.append('wm_type', t);
      if (t === 'image') { fd.append('wm_size', size.value); if (logo.file) fd.append(prefix + 'image', logo.file); }
      if (t === 'text') fd.append(prefix + 'text', text.value);
      if (t === 'binary') { fd.append(prefix + 'binary', bin.value); if (!emb) fd.append('wm_bits', nbits.value); }
    },
    set(item) {
      const c = item.config;
      type.set(c.wm_type); show(c.wm_type);
      if (c.wm_type === 'image') size.value = c.wm_size;
      if (c.wm_type === 'text') { text.value = item.wm_text || ''; text.dispatchEvent(new Event('input')); }
      if (c.wm_type === 'binary') { bin.value = item.wm_binary || ''; bin.dispatchEvent(new Event('input')); }
    },
  };
}

/* ================= tampilan hasil ================= */
function metricCard(name, value, unit, status, note) {
  return h('div', { class: 'metric ' + status }, h('span', { class: 'm-name' }, name),
    h('strong', {}, value, unit && h('small', {}, unit)), h('span', { class: 'm-note' }, note));
}

function metricsPanel(m) {
  const cards = [];
  if (m.psnr != null) cards.push(metricCard('PSNR', m.psnr.toFixed(2), 'dB', m.psnr > 35 ? 'good' : m.psnr > 30 ? 'warn' : 'bad',
    m.psnr > 35 ? 'Tidak terlihat (target > 35 dB)' : 'Perubahan mulai terlihat'));
  if (m.ssim != null) cards.push(metricCard('SSIM', m.ssim.toFixed(4), '', m.ssim > 0.95 ? 'good' : m.ssim > 0.9 ? 'warn' : 'bad',
    m.ssim > 0.95 ? 'Struktur terjaga (target > 0,95)' : 'Struktur mulai berubah'));
  if (m.ber === null) cards.push(metricCard('BER', '—', '', 'neutral', 'Watermark asli tidak diberikan'));
  else if (m.ber !== undefined) {
    const s = m.ber === 0 ? ['good', 'Pulih sempurna'] : m.ber <= 5 ? ['good', 'Hampir sempurna'] : m.ber <= 20 ? ['warn', 'Sebagian rusak'] : ['bad', 'Rusak'];
    cards.push(metricCard('BER', m.ber.toFixed(2), '%', s[0], `${s[1]} · ${m.bit_errors} dari ${m.n_bits} bit salah`));
  }
  return h('div', { class: 'metrics' }, cards);
}

const fig = (url, caption) => h('figure', {}, h('img', { class: 'photo', src: url, alt: caption, loading: 'lazy' }), h('figcaption', {}, caption));

function textBox(val, ref) {
  if (val == null) return h('p', { class: 'hint' }, 'Tidak diberikan');
  if (ref == null) return h('div', { class: 'textbox' }, val);
  return h('div', { class: 'textbox' }, [...val].map((c, i) => (ref[i] === c ? c : h('span', { class: 'x' }, c))));
}

function wmCompare(item) {
  const t = item.config.wm_type, u = item.urls || {};
  const box = (cap, node) => h('div', { class: 'wmbox' }, node, h('span', { class: 'hint' }, cap));
  if (t === 'image') {
    const im = (url, alt) => url ? h('img', { class: 'pix', src: url, alt }) : h('p', { class: 'hint' }, 'Tidak diberikan');
    return h('div', { class: 'wmpair' }, box('Watermark asli', im(u.wm_original, 'Watermark asli')), box('Hasil ekstraksi', im(u.wm_extracted, 'Watermark hasil ekstraksi')));
  }
  const orig = t === 'text' ? (item.wm_text ?? item.expected?.text) : (item.wm_binary ?? item.expected?.binary);
  const ext = t === 'text' ? item.extracted?.text : item.extracted?.binary;
  return h('div', { class: 'wmpair' }, box('Watermark asli', textBox(orig, null)), box('Hasil ekstraksi (huruf merah = salah)', textBox(ext, orig)));
}

const notesList = item => item.notes && item.notes.length ? h('ul', { class: 'notes' }, item.notes.map(n => h('li', {}, n))) : null;
const cfgChips = c => [wvLabel(c.wavelet), `Level ${c.level}`, `Δ ${c.delta}`, `Kunci ${c.key}`, WM_TYPE[c.wm_type]].map(t => h('span', { class: 'chip' }, t));

function embedResult(item) {
  const u = item.urls;
  return h('div', { class: 'stack' }, notesList(item),
    card(h('h2', {}, 'Perbandingan visual'), h('div', { class: 'grid3', style: 'margin-top:14px' },
      fig(u.cover, 'Citra asli'), fig(u.watermarked, 'Ber-watermark'), fig(u.diff, 'Selisih diperbesar 20×'))),
    card(h('h2', {}, 'Evaluasi kinerja'), h('div', { style: 'margin:14px 0 8px' }, metricsPanel(item.metrics)),
      h('p', { class: 'hint' }, `Redundansi: tiap bit disisipkan ${item.config.redundancy}× di posisi acak. Ukuran citra ${item.config.width}×${item.config.height} px.`)),
    card(h('h2', {}, 'Ekstraksi langsung (tanpa serangan)'), h('div', { style: 'margin-top:14px' }, wmCompare(item))),
    h('div', { class: 'row' },
      h('a', { class: 'btn', href: u.watermarked + '&download=1' }, 'Unduh citra ber-watermark'),
      h('a', { class: 'btn ghost', href: `/api/history/${item.id}/config?sid=${SID}` }, 'Unduh kunci dan parameter'),
      h('button', { class: 'btn ghost', type: 'button', onclick: () => { state.pending = { attack: item.id }; go('serangan'); } }, 'Uji ketahanan')));
}

/* ================= badge & router ================= */
async function refreshBadge() {
  try {
    const st = await api('/stats');
    const b = $('#badge');
    if (b) { b.textContent = st.total; b.hidden = !st.total; }
  } catch { /* abaikan */ }
}

/* ================= Beranda ================= */
async function viewHome(root) {
  const band = (n, d, c) => h('div', { class: 'band ' + c }, n, h('small', {}, d));
  root.append(h('div', { class: 'hero' },
    h('div', {},
      h('h1', {}, 'Sisipkan tanda hak cipta yang tak terlihat, lalu ukur seberapa tahan.'),
      h('p', { class: 'lead' }, 'Watermark disisipkan ke koefisien frekuensi citra lewat DWT, sehingga mata tidak melihat perubahannya. Uji dengan kompresi JPEG, pemotongan, pengubahan ukuran, dan derau.'),
      h('div', { class: 'row' }, linkBtn('Sisipkan watermark', 'sisip'), linkBtn('Ekstrak watermark', 'ekstraksi', true), linkBtn('Simulasi serangan', 'serangan', true))),
    h('div', { class: 'bandmap', role: 'img', 'aria-label': 'Peta sub-band DWT: LL kiri atas, HL kanan atas dan LH kiri bawah adalah tempat watermark, HH kanan bawah' },
      band('LL', 'Gambaran umum', 'll'), band('HL', 'Tepi vertikal · watermark', 'hot'), band('LH', 'Tepi horizontal · watermark', 'hot'), band('HH', 'Derau halus', 'hh'))));

  let st = { total: 0, counts: {}, avg_psnr: null, avg_ber: null, recent: [] };
  try { st = await api('/stats'); } catch (e) { toast(e.message, true); }
  const stat = (l, v, s) => h('div', { class: 'stat' }, h('span', {}, l), h('strong', {}, v), h('small', {}, s));
  root.append(h('div', { class: 'stats' },
    stat('Citra diproses', st.total, `${st.counts.embed || 0} sisip · ${st.counts.extract || 0} ekstraksi · ${st.counts.attack || 0} serangan`),
    stat('Rata-rata PSNR', st.avg_psnr == null ? '—' : st.avg_psnr.toFixed(1) + ' dB', 'Kualitas visual hasil penyisipan (target > 35 dB)'),
    stat('Rata-rata BER', st.avg_ber == null ? '—' : st.avg_ber.toFixed(2) + '%', 'Kesalahan bit pada ekstraksi dan serangan; makin kecil makin baik')));

  if (!st.recent.length) {
    root.append(emptyState('Belum ada citra yang diproses', 'Mulai dengan menyisipkan watermark ke satu citra. Logo bawaan tersedia bila Anda belum punya.', linkBtn('Mulai menyisipkan', 'sisip')));
    return;
  }
  root.append(h('h2', { style: 'margin-bottom:12px' }, 'Terakhir diproses'),
    h('div', { class: 'strip' }, st.recent.map(i => h('a', { href: '#/riwayat', class: 'hcard', style: 'text-decoration:none;color:inherit' },
      h('img', { src: i.urls.thumb, alt: i.title, style: 'aspect-ratio:4/3;object-fit:cover;width:100%' }),
      h('div', { class: 'hbody' }, h('span', { class: 'chip ' + i.kind, style: 'justify-self:start' }, KIND[i.kind]), h('span', { class: 't' }, i.title))))));
}

/* ================= Penyisipan ================= */
function viewEmbed(root, pend) {
  const reuse = takeNote(pend, 'reuse');
  root.append(pageHead('Penyisipan watermark', 'Pilih citra dan watermark, atur parameter DWT, lalu sisipkan. Hasil langsung dibandingkan dengan citra asli.'));
  let reuseId = reuse ? reuse.id : null;
  const cover = dropzone({ label: 'Unggah citra asli', hint: 'PNG atau JPG · maks. 16 MB · diproses hingga 1024 px', onClear: () => { reuseId = null; } });
  const wm = wmInput('embed');
  const params = paramsPanel();
  const out = h('div', {}, emptyState('Hasil akan tampil di sini', 'Unggah citra, atur watermark dan parameter, lalu klik “Sisipkan watermark”.'));
  if (reuse) { cover.setUrl(reuse.urls.cover); params.set(reuse.config); wm.set(reuse); }

  const btn = h('button', { class: 'btn', type: 'button' }, 'Sisipkan watermark');
  btn.addEventListener('click', () => withBusy(btn, 'Memproses…', async () => {
    if (!cover.file && !reuseId) { toast('Unggah citra asli terlebih dahulu.', true); return; }
    const fd = new FormData();
    if (cover.file) fd.append('cover', cover.file);
    if (reuseId) fd.append('reuse_id', reuseId);
    params.append(fd); wm.append(fd);
    try {
      const { item } = await api('/embed', { method: 'POST', form: fd });
      out.replaceChildren(embedResult(item));
      refreshBadge();
      out.scrollIntoView({ behavior: 'smooth', block: 'start' });
    } catch (e) { toast(e.message, true); }
  }));

  root.append(h('div', { class: 'cols' },
    h('div', { class: 'stack' },
      card(h('h2', {}, 'Citra asli'), h('div', { style: 'margin-top:12px' }, cover.el)),
      card(h('h2', {}, 'Watermark'), h('div', { style: 'margin-top:12px' }, wm.el)),
      card(h('h2', {}, 'Parameter DWT'), h('div', { style: 'margin-top:12px' }, params.el)),
      btn),
    out));
}

/* ================= Ekstraksi ================= */
async function viewExtract(root, pend) {
  const pre = takeNote(pend, 'extractRef');
  root.append(pageHead('Ekstraksi watermark', 'Buktikan apakah watermark masih terbaca. Pilih hasil dari riwayat, atau unggah citra dan isi parameter yang sama dengan saat penyisipan.'));
  let items = [];
  try { items = (await api('/history')).items.filter(i => i.kind === 'embed' || i.kind === 'attack'); } catch (e) { toast(e.message, true); }

  const mode = segmented([{ value: 'history', label: 'Dari riwayat' }, { value: 'upload', label: 'Unggah citra' }],
    pre || items.length ? 'history' : 'upload', () => sync());
  const sel = h('select', {}, items.map(i => h('option', { value: i.id }, `${KIND[i.kind]} · ${i.title}`)));
  if (pre) sel.value = pre;
  const summary = h('div', { class: 'row' });
  const showSummary = () => { const it = items.find(i => i.id === sel.value); summary.replaceChildren(...(it ? cfgChips(it.config) : [])); };
  sel.addEventListener('change', showSummary); showSummary();
  const other = dropzone({ label: 'Citra uji lain (opsional)', hint: 'Mis. hasil unduhan atau tangkapan layar yang sudah diserang', compact: true });

  const test = dropzone({ label: 'Unggah citra uji', hint: 'Citra ber-watermark, bersih maupun yang sudah diserang' });
  const params = paramsPanel();
  const wm = wmInput('extract');
  const rw = h('input', { type: 'number', min: 8, placeholder: 'otomatis' });
  const rh = h('input', { type: 'number', min: 8, placeholder: 'otomatis' });

  const histPanel = h('div', {}, items.length
    ? h('div', { class: 'stack' }, field('Sumber citra dan parameter', sel), summary, other.el)
    : emptyState('Riwayat masih kosong', 'Sisipkan watermark dulu, atau pindah ke “Unggah citra”.', linkBtn('Ke penyisipan', 'sisip')));
  const upPanel = h('div', { class: 'stack' }, test.el,
    h('div', {}, h('h3', { style: 'margin-bottom:10px' }, 'Parameter (sama dengan saat penyisipan)'), params.el),
    h('div', {}, h('h3', { style: 'margin-bottom:10px' }, 'Watermark'), wm.el),
    h('div', {}, h('h3', { style: 'margin-bottom:10px' }, 'Ukuran citra saat penyisipan (opsional)'),
      h('div', { class: 'grid2' }, field('Lebar (px)', rw), field('Tinggi (px)', rh)),
      h('p', { class: 'hint', style: 'margin-top:6px' }, 'Isi bila citra uji berubah ukuran; citra akan disesuaikan. Kosong = pakai ukuran citra uji.')));
  function sync() { histPanel.hidden = mode.get() !== 'history'; upPanel.hidden = mode.get() !== 'upload'; }
  sync();

  const out = h('div', {}, emptyState('Hasil ekstraksi akan tampil di sini', 'Pilih sumber di sebelah kiri, lalu klik “Ekstrak watermark”.'));
  const btn = h('button', { class: 'btn', type: 'button' }, 'Ekstrak watermark');
  btn.addEventListener('click', () => withBusy(btn, 'Mengekstrak…', async () => {
    const fd = new FormData();
    if (mode.get() === 'history') {
      if (!sel.value) { toast('Belum ada item riwayat untuk diekstrak.', true); return; }
      fd.append('ref_id', sel.value);
      if (other.file) fd.append('image', other.file);
    } else {
      if (!test.file) { toast('Unggah citra uji terlebih dahulu.', true); return; }
      fd.append('image', test.file); params.append(fd); wm.append(fd);
      if (rw.value) fd.append('ref_w', rw.value);
      if (rh.value) fd.append('ref_h', rh.value);
    }
    try {
      const { item } = await api('/extract', { method: 'POST', form: fd });
      out.replaceChildren(h('div', { class: 'stack' }, notesList(item),
        card(h('h2', {}, 'Citra yang diuji'), h('div', { style: 'margin-top:12px;max-width:380px' }, fig(item.urls.input, 'Citra uji'))),
        card(h('h2', {}, 'Watermark hasil ekstraksi'), h('div', { style: 'margin-top:14px' }, wmCompare(item))),
        card(h('h2', {}, 'Evaluasi kinerja'), h('div', { style: 'margin-top:14px' }, metricsPanel(item.metrics)))));
      refreshBadge();
    } catch (e) { toast(e.message, true); }
  }));
  root.append(h('div', { class: 'cols' }, h('div', { class: 'stack' }, card(h('h2', {}, 'Sumber'), h('div', { style: 'margin:12px 0' }, mode.el), histPanel, upPanel), btn), out));
}

/* ================= Simulasi serangan ================= */
async function viewAttack(root, pend) {
  const pre = takeNote(pend, 'attack');
  root.append(pageHead('Simulasi serangan', 'Rusak citra ber-watermark dengan serangan yang Anda atur, lalu lihat apakah watermark masih terbaca. Urutan penerapan: pemotongan, resize, derau, lalu JPEG.'));
  let items = [];
  try { items = (await api('/history')).items.filter(i => i.kind === 'embed'); } catch (e) { toast(e.message, true); }
  if (!items.length) {
    root.append(emptyState('Belum ada citra ber-watermark', 'Sisipkan watermark terlebih dahulu; hasilnya otomatis muncul di sini.', linkBtn('Ke penyisipan', 'sisip')));
    return;
  }
  const sel = h('select', {}, items.map(i => h('option', { value: i.id }, i.title)));
  if (pre) sel.value = pre;
  const cur = () => items.find(i => i.id === sel.value);

  /* panggung + alat crop interaktif */
  const img = h('img', { alt: 'Citra ber-watermark yang akan diserang', draggable: 'false' });
  const box = h('div', { class: 'cropbox', hidden: true });
  const stage = h('div', { class: 'stage' }, img, box);
  const areaLbl = h('p', { class: 'hint' });
  let rect = null, drag = null;
  const block = (title, body, open = false) => {
    const cb = h('input', { type: 'checkbox' });
    const bd = h('div', { class: 'attack-body', hidden: !open }, body);
    cb.checked = open;
    cb.addEventListener('change', () => { bd.hidden = !cb.checked; if (title === 'Pemotongan (cropping)') drawCrop(); });
    return { el: h('div', { class: 'attack-block' }, h('label', { class: 'row', style: 'cursor:pointer;font-weight:600' }, cb, title), bd), on: () => cb.checked };
  };
  function drawCrop() {
    const active = crop.on();
    stage.classList.toggle('cropping', active);
    const ok = rect && rect.w * rect.h > 0;
    box.hidden = !ok;
    if (ok) Object.assign(box.style, { left: rect.x * 100 + '%', top: rect.y * 100 + '%', width: rect.w * 100 + '%', height: rect.h * 100 + '%' });
    areaLbl.textContent = ok ? `Area yang dihapus: ${(rect.w * rect.h * 100).toFixed(0)}% dari citra.` : 'Aktifkan pemotongan lalu seret pada citra untuk memilih area, atau pilih ukuran cepat.';
  }
  const pt = e => { const b = img.getBoundingClientRect(); return [clamp((e.clientX - b.left) / b.width), clamp((e.clientY - b.top) / b.height)]; };
  stage.addEventListener('pointerdown', e => {
    if (!crop.on()) return;
    const [x, y] = pt(e); drag = { x, y }; stage.setPointerCapture(e.pointerId); rect = { x, y, w: 0, h: 0 }; drawCrop(); e.preventDefault();
  });
  stage.addEventListener('pointermove', e => {
    if (!drag) return;
    const [x, y] = pt(e);
    rect = { x: Math.min(drag.x, x), y: Math.min(drag.y, y), w: Math.abs(x - drag.x), h: Math.abs(y - drag.y) }; drawCrop();
  });
  const endDrag = () => { drag = null; };
  stage.addEventListener('pointerup', endDrag); stage.addEventListener('pointercancel', endDrag);
  const quick = p => { const f = Math.sqrt(p / 100); rect = { x: 1 - f, y: 1 - f, w: f, h: f }; drawCrop(); };

  const jq = rangeField({ label: 'Kualitas JPEG', min: 10, max: 100, step: 5, value: 50, fmt: v => `Q = ${v}`, hint: 'Makin rendah, makin kuat kompresinya.' });
  const rs = rangeField({ label: 'Skala (turun lalu naik lagi)', min: 0.2, max: 0.95, step: 0.05, value: 0.5, fmt: v => `${(+v).toFixed(2)}×` });
  const ns = rangeField({ label: 'Derau Gaussian', min: 1, max: 50, step: 1, value: 10, fmt: v => `σ = ${v}` });
  const jpeg = block('Kompresi JPEG', jq.el, true);
  const crop = block('Pemotongan (cropping)', h('div', {},
    h('div', { class: 'row' }, [10, 25, 50].map(p => h('button', { class: 'btn ghost sm', type: 'button', onclick: () => quick(p) }, `${p}% di pojok`)),
      h('button', { class: 'btn ghost sm', type: 'button', onclick: () => { rect = null; drawCrop(); } }, 'Reset area')), areaLbl));
  const resize = block('Resize (turun lalu naik)', rs.el);
  const noise = block('Derau acak', ns.el);

  const result = h('div', {});
  const bench = h('div', {});
  function setImage() { img.src = cur().urls.watermarked; rect = null; drawCrop(); result.replaceChildren(); bench.replaceChildren(); }
  sel.addEventListener('change', setImage);

  const steps = () => {
    const s = [];
    if (crop.on()) {
      if (!rect || rect.w * rect.h <= 0) { toast('Seret pada citra untuk memilih area pemotongan.', true); return null; }
      s.push({ type: 'crop_rect', ...rect });
    }
    if (resize.on()) s.push({ type: 'resize', scale: rs.get() });
    if (noise.on()) s.push({ type: 'noise', sigma: ns.get() });
    if (jpeg.on()) s.push({ type: 'jpeg', quality: jq.get() });
    if (!s.length) { toast('Pilih minimal satu serangan.', true); return null; }
    return s;
  };

  const run = h('button', { class: 'btn', type: 'button' }, 'Terapkan serangan');
  run.addEventListener('click', () => withBusy(run, 'Menyerang…', async () => {
    const s = steps(); if (!s) return;
    try {
      const { item } = await api('/attack', { method: 'POST', json: { ref_id: sel.value, attacks: s } });
      result.replaceChildren(h('div', { class: 'stack', style: 'margin-top:16px' },
        card(h('h2', {}, 'Hasil serangan: ' + item.title), h('div', { class: 'grid2', style: 'margin-top:14px' }, fig(cur().urls.watermarked, 'Sebelum serangan'), fig(item.urls.attacked, 'Setelah serangan')),
          h('div', { class: 'row', style: 'margin-top:12px' }, h('a', { class: 'btn ghost sm', href: item.urls.attacked + '&download=1' }, 'Unduh citra setelah serangan'),
            h('button', { class: 'btn ghost sm', type: 'button', onclick: () => { state.pending = { extractRef: item.id }; go('ekstraksi'); } }, 'Buka di ekstraksi'))),
        card(h('h2', {}, 'Watermark setelah serangan'), h('div', { style: 'margin-top:14px' }, wmCompare(item))),
        card(h('h2', {}, 'Evaluasi kinerja'), h('div', { style: 'margin:14px 0 8px' }, metricsPanel(item.metrics)), h('p', { class: 'hint' }, 'PSNR dan SSIM dihitung terhadap citra asli sebelum penyisipan.'))));
      refreshBadge();
    } catch (e) { toast(e.message, true); }
  }));

  const benchBtn = h('button', { class: 'btn ghost', type: 'button' }, 'Uji semua serangan otomatis');
  benchBtn.addEventListener('click', () => withBusy(benchBtn, 'Menguji 13 serangan…', async () => {
    try {
      const { rows } = await api('/benchmark', { method: 'POST', json: { ref_id: sel.value } });
      bench.replaceChildren(card(h('h2', {}, 'Ketahanan terhadap 13 serangan standar'),
        h('p', { class: 'hint', style: 'margin:6px 0 12px' }, 'Bar menunjukkan BER; makin pendek makin baik. Kolom kanan: PSNR citra setelah serangan.'),
        h('div', { class: 'bars' }, rows.map(r => h('div', { class: 'barrow' }, h('span', {}, r.name),
          h('div', { class: 'bar', role: 'img', 'aria-label': `BER ${r.ber}%` }, h('i', { class: r.ber <= 5 ? '' : r.ber <= 20 ? 'warn' : 'bad', style: `width:${Math.max(clamp(r.ber / 50) * 100, 1)}%` })),
          h('span', { class: 'v' }, r.ber.toFixed(2) + '%'), h('span', { class: 'q' }, r.psnr.toFixed(1) + ' dB'))))));
    } catch (e) { toast(e.message, true); }
  }));

  root.append(h('div', { class: 'cols' },
    h('div', { class: 'stack' },
      card(h('h2', {}, 'Citra target'), h('div', { style: 'margin-top:12px' }, field('Pilih hasil penyisipan', sel))),
      card(h('h2', {}, 'Panel serangan'), h('div', { style: 'margin-top:12px' }, jpeg.el, crop.el, resize.el, noise.el)),
      h('div', { class: 'row' }, run, benchBtn)),
    h('div', {}, card(h('h2', {}, 'Pratinjau'), h('div', { style: 'margin-top:12px' }, stage)), result, h('div', { style: 'margin-top:16px' }, bench))));
  setImage();
}

/* ================= Riwayat ================= */
function kvTable(item) {
  const c = item.config;
  const rows = [['Dibuat', fmtDate(item.created_at)], ['Wavelet', wvLabel(c.wavelet)], ['Level dekomposisi', c.level], ['Alpha (Δ)', c.delta], ['Kunci', c.key],
    ['Jenis watermark', WM_TYPE[c.wm_type]], ['Jumlah bit', c.n_bits], ['Ukuran citra', c.width ? `${c.width} × ${c.height} px` : null], ['Redundansi', c.redundancy ? c.redundancy + '×' : null]];
  return h('table', { class: 'kv' }, h('tbody', {}, rows.filter(r => r[1] != null).map(r => h('tr', {}, h('td', {}, r[0]), h('td', {}, String(r[1]))))));
}

function openDialog(item) {
  const names = { cover: 'Citra asli', watermarked: 'Ber-watermark', diff: 'Selisih ×20', attacked: 'Setelah serangan', input: 'Citra uji' };
  const dlg = h('dialog', {});
  const imgs = item.files.filter(f => names[f]).map(f => fig(item.urls[f], names[f]));
  dlg.append(h('div', { class: 'dlg' },
    h('div', { class: 'dlg-head' }, h('div', {}, h('span', { class: 'chip ' + item.kind }, KIND[item.kind]), h('h2', { style: 'margin-top:6px' }, item.title)),
      h('button', { class: 'btn ghost sm', type: 'button', onclick: () => dlg.close() }, 'Tutup')),
    h('div', { class: 'grid3' }, imgs), metricsPanel(item.metrics), wmCompare(item), kvTable(item)));
  dlg.addEventListener('close', () => dlg.remove());
  dlg.addEventListener('click', e => { if (e.target === dlg) dlg.close(); });
  document.body.append(dlg); dlg.showModal();
}

async function viewHistory(root) {
  root.append(pageHead('Riwayat dan galeri', 'Semua hasil sesi ini tersimpan. Buka kembali untuk menguji parameter lain tanpa mengunggah ulang citra.'));
  let items = [], filter = 'all';
  const grid = h('div', { class: 'gallery' });
  const filters = segmented([{ value: 'all', label: 'Semua' }, { value: 'embed', label: 'Penyisipan' }, { value: 'extract', label: 'Ekstraksi' }, { value: 'attack', label: 'Serangan' }], 'all', v => { filter = v; draw(); });
  const clearBtn = h('button', { class: 'btn danger sm', type: 'button', onclick: async () => {
    if (!confirm('Hapus seluruh riwayat sesi ini?')) return;
    try { await api('/history', { method: 'DELETE' }); items = []; draw(); refreshBadge(); toast('Riwayat dikosongkan.'); } catch (e) { toast(e.message, true); }
  } }, 'Kosongkan riwayat');
  root.append(h('div', { class: 'row', style: 'justify-content:space-between;margin-bottom:16px' }, filters.el, clearBtn), grid);

  const line = i => {
    const m = i.metrics || {};
    if (i.kind === 'embed') return `PSNR ${m.psnr.toFixed(1)} dB · SSIM ${m.ssim.toFixed(3)} · BER ${m.ber}%`;
    if (i.kind === 'attack') return `BER ${m.ber.toFixed(2)}% · PSNR ${m.psnr.toFixed(1)} dB`;
    return m.ber == null ? 'BER tidak dihitung' : `BER ${m.ber.toFixed(2)}%`;
  };
  const del = async i => {
    if (!confirm('Hapus item ini dari riwayat?')) return;
    try { await api('/history/' + i.id, { method: 'DELETE' }); items = items.filter(x => x.id !== i.id); draw(); refreshBadge(); } catch (e) { toast(e.message, true); }
  };
  const act = (label, fn, cls = 'ghost') => h('button', { class: `btn ${cls} sm`, type: 'button', onclick: fn }, label);
  const download = i => (i.urls.watermarked || i.urls.attacked) && h('a', { class: 'btn ghost sm', href: (i.urls.watermarked || i.urls.attacked) + '&download=1' }, 'Unduh');

  function draw() {
    const list = items.filter(i => filter === 'all' || i.kind === filter);
    if (!list.length) { grid.replaceChildren(emptyState('Tidak ada item', 'Hasil penyisipan, ekstraksi, dan serangan akan muncul di sini.', linkBtn('Mulai menyisipkan', 'sisip'))); return; }
    grid.replaceChildren(...list.map(i => h('article', { class: 'hcard' },
      h('button', { class: 'thumb', type: 'button', 'aria-label': 'Lihat detail ' + i.title, onclick: () => openDialog(i) }, h('img', { src: i.urls.thumb, alt: '', loading: 'lazy' })),
      h('div', { class: 'hbody' }, h('span', { class: 'chip ' + i.kind, style: 'justify-self:start' }, KIND[i.kind]), h('span', { class: 't' }, i.title),
        h('span', { class: 'm' }, line(i)), h('span', { class: 'm' }, fmtDate(i.created_at))),
      h('div', { class: 'hact' },
        i.kind === 'embed' && act('Sisipkan ulang', () => { state.pending = { reuse: i }; go('sisip'); }),
        i.kind === 'embed' && act('Uji serangan', () => { state.pending = { attack: i.id }; go('serangan'); }),
        i.kind !== 'extract' && act('Ekstrak', () => { state.pending = { extractRef: i.id }; go('ekstraksi'); }),
        download(i), act('Hapus', () => del(i), 'danger')))));
  }
  try { items = (await api('/history')).items; } catch (e) { toast(e.message, true); }
  draw();
}

/* ================= router & init ================= */
const ICONS = {
  home: '<path d="M3 11l9-8 9 8"/><path d="M5 10v10h14V10"/>',
  embed: '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M8 12h8M12 8v8"/>',
  extract: '<circle cx="11" cy="11" r="7"/><path d="M21 21l-5-5"/>',
  attack: '<path d="M13 2L4 14h7l-1 8 9-12h-7z"/>',
  history: '<path d="M3 12a9 9 0 109-9 9 9 0 00-7 3.4"/><path d="M3 4v4h4M12 7v5l3 2"/>',
};
const icon = n => h('span', { html: `<svg viewBox="0 0 24 24" aria-hidden="true">${ICONS[n]}</svg>` });
const ROUTES = [
  { key: 'beranda', label: 'Beranda', icon: 'home', view: viewHome },
  { key: 'sisip', label: 'Penyisipan', icon: 'embed', view: viewEmbed },
  { key: 'ekstraksi', label: 'Ekstraksi', icon: 'extract', view: viewExtract },
  { key: 'serangan', label: 'Simulasi serangan', icon: 'attack', view: viewAttack },
  { key: 'riwayat', label: 'Riwayat', icon: 'history', view: viewHistory },
];

function buildNav() {
  $('#nav').replaceChildren(...ROUTES.map(r => h('a', { href: '#/' + r.key, 'data-key': r.key }, icon(r.icon), r.label,
    r.key === 'riwayat' ? h('span', { class: 'badge', id: 'badge', hidden: true }, '0') : null)));
}

function render() {
  const key = location.hash.replace(/^#\/?/, '') || 'beranda';
  const route = ROUTES.find(r => r.key === key) || ROUTES[0];
  document.querySelectorAll('#nav a').forEach(a => (a.dataset.key === route.key ? a.setAttribute('aria-current', 'page') : a.removeAttribute('aria-current')));
  const pend = state.pending; state.pending = null;
  const main = $('#main'); main.replaceChildren();
  document.title = `${route.label} · Lab Watermark DWT`;
  window.scrollTo(0, 0);
  Promise.resolve(route.view(main, pend)).catch(e => { console.error(e); toast('Tampilan gagal dimuat: ' + e.message, true); });
}

async function init() {
  buildNav();
  $('#new-session').addEventListener('click', () => {
    if (!confirm('Mulai sesi baru? Riwayat sesi saat ini tidak akan tampil lagi di browser ini.')) return;
    SID = newSid(); try { localStorage.setItem('wm_sid', SID); } catch {}
    refreshBadge(); render(); toast('Sesi baru dimulai.');
  });
  try { state.options = await api('/options'); }
  catch (e) { $('#main').append(emptyState('Server tidak merespons', e.message)); return; }
  $('#env-note').textContent = state.options.has_pywt ? 'PyWavelets terpasang (Haar, Db4)' : 'Mode Haar · PyWavelets belum terpasang';
  window.addEventListener('hashchange', render);
  render(); refreshBadge();
}
init();
})();
