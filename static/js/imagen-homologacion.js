/* Genera una imagen (PNG) de la homologación para enviar por WhatsApp. */
(function () {
    'use strict';
    const W = 1080, PAD = 64;
    const C = {
        green: '#7fb536', green2: '#527a1f', greenSoft: '#eef6e3', ink: '#13201a', text2: '#4a5850', text3: '#87938b',
        line: '#e3e8de', card: '#f6f8f3', pink: '#e6007e', pinkSoft: '#fde6f2', dark: '#0c1a12', white: '#ffffff',
    };
    const DISPLAY = 'Outfit, "Segoe UI", system-ui, sans-serif';
    const BODY = 'Inter, "Segoe UI", system-ui, sans-serif';
    const money = (n) => '$' + Math.round(Number(n) || 0).toLocaleString('es-CO');

    function font(ctx, weight, size, fam) { ctx.font = `${weight} ${size}px ${fam}`; }
    function rr(ctx, x, y, w, h, r) {
        ctx.beginPath(); ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r);
        ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath();
    }
    function wrap(ctx, text, maxW, maxLines = 3) {
        const words = String(text || '').split(/\s+/); const lines = []; let line = '';
        for (const w of words) {
            const t = line ? line + ' ' + w : w;
            if (ctx.measureText(t).width > maxW && line) { lines.push(line); line = w; } else line = t;
        }
        if (line) lines.push(line);
        if (lines.length > maxLines) { const cut = lines.slice(0, maxLines); cut[maxLines - 1] = cut[maxLines - 1].replace(/\s*\S*$/, '') + '…'; return cut; }
        return lines;
    }
    function check(ctx, cx, cy, r, bg, fg) {
        ctx.fillStyle = bg; ctx.beginPath(); ctx.arc(cx, cy, r, 0, Math.PI * 2); ctx.fill();
        ctx.strokeStyle = fg; ctx.lineWidth = r * 0.22; ctx.lineCap = 'round'; ctx.lineJoin = 'round';
        ctx.beginPath(); ctx.moveTo(cx - r * 0.42, cy + r * 0.02); ctx.lineTo(cx - r * 0.1, cy + r * 0.34); ctx.lineTo(cx + r * 0.45, cy - r * 0.3); ctx.stroke();
    }
    function chip(ctx, x, y, text, bg, fg, h = 50) {
        font(ctx, 700, 21, BODY);
        const w = ctx.measureText(text).width + 40;
        ctx.fillStyle = bg; rr(ctx, x, y, w, h, h / 2); ctx.fill();
        ctx.fillStyle = fg; ctx.textBaseline = 'middle'; ctx.fillText(text, x + 20, y + h / 2 + 1); ctx.textBaseline = 'alphabetic';
        return w;
    }
    function loadImg(src) {
        return new Promise((res) => { const i = new Image(); i.onload = () => res(i); i.onerror = () => res(null); i.src = src; });
    }

    // Textos de los chips (precio / inicio) y si caben en una sola fila
    const CHIPS_W = W - PAD * 2 - 300 - 44;
    function textosChips(ctx, p, conPrecio) {
        const pr = p.precio;
        const precio = conPrecio && pr
            ? (pr.descuento ? `${pr.descuento}% ${pr.tipo_descuento === 'SENA' ? 'SENA' : 'dcto.'}: ${money(pr.valor_final)}/semestre` : `Semestre: ${money(pr.valor)}`)
            : null;
        const inicio = p.inicio ? `Inicio: ${p.inicio.replace(/ de (\d{4})$/, ' $1')}` : null;
        font(ctx, 700, 21, BODY);
        const wp = precio ? ctx.measureText(precio).width + 40 : 0;
        const wi = inicio ? ctx.measureText(inicio).width + 40 : 0;
        const dosFilas = !!(precio && inicio) && wp + 12 + wi > CHIPS_W;
        return { precio, inicio, dosFilas };
    }

    function medirPrograma(ctx, p, conPrecio) {
        font(ctx, 700, 36, DISPLAY);
        const nameLines = wrap(ctx, p.programa_display, 600, 2);
        let h = 48 + nameLines.length * 44 + 20 + 58 + 18 + 30;
        const t = textosChips(ctx, p, conPrecio);
        if (t.precio || t.inicio) h += 26 + 50 + (t.dosFilas ? 62 : 0);
        return { nameLines, h: Math.max(h + 40, 300) };
    }

    function dibujarPrograma(ctx, p, y, m, conPrecio) {
        const x = PAD, w = W - PAD * 2, h = m.h;
        ctx.fillStyle = C.card; rr(ctx, x, y, w, h, 34); ctx.fill();
        ctx.strokeStyle = C.line; ctx.lineWidth = 2; rr(ctx, x, y, w, h, 34); ctx.stroke();

        // Dona: % de la carrera homologada
        const cx = x + 150, cy = y + h / 2, r = 98, lw = 28;
        const pct = Math.max(0, Math.min(100, p.porcentaje || 0));
        ctx.lineCap = 'round'; ctx.lineWidth = lw; ctx.strokeStyle = C.line;
        ctx.beginPath(); ctx.arc(cx, cy, r, 0, Math.PI * 2); ctx.stroke();
        const g = ctx.createLinearGradient(cx - r, cy - r, cx + r, cy + r); g.addColorStop(0, '#a6d65f'); g.addColorStop(1, C.green2);
        ctx.strokeStyle = g; ctx.beginPath(); ctx.arc(cx, cy, r, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * pct / 100); ctx.stroke();
        ctx.textAlign = 'center'; ctx.fillStyle = C.ink; font(ctx, 800, 56, DISPLAY); ctx.fillText(`${pct}%`, cx, cy + 14);
        ctx.fillStyle = C.text2; font(ctx, 600, 19, BODY); ctx.fillText('homologado', cx, cy + 46); ctx.textAlign = 'left';

        // Contenido
        const x0 = x + 300, maxW = w - 300 - 44;
        let yy = y + 48 + 32;
        ctx.fillStyle = C.ink; font(ctx, 700, 36, DISPLAY);
        m.nameLines.forEach((l) => { ctx.fillText(l, x0, yy); yy += 44; });
        yy += 4;

        // Barra de semestres
        const n = Math.max(1, p.total || (p.homologados + p.faltantes)); const gap = 10;
        const size = Math.min(58, (maxW - gap * (n - 1)) / n);
        for (let i = 0; i < n; i++) {
            const sx = x0 + i * (size + gap), done = i < p.homologados;
            ctx.fillStyle = done ? C.green : C.white; rr(ctx, sx, yy, size, 58, 14); ctx.fill();
            if (!done) { ctx.strokeStyle = '#cfd8c7'; ctx.lineWidth = 2; rr(ctx, sx, yy, size, 58, 14); ctx.stroke(); }
            ctx.fillStyle = done ? C.white : C.text3; font(ctx, 700, size > 44 ? 18 : 14, BODY); ctx.textAlign = 'center';
            ctx.fillText(`S${i + 1}`, sx + size / 2, yy + 36); ctx.textAlign = 'left';
        }
        yy += 58 + 40;
        font(ctx, 800, 23, BODY); ctx.fillStyle = C.green2; const a = `${p.homologados} semestres homologados`; ctx.fillText(a, x0, yy);
        let lx = x0 + ctx.measureText(a).width; font(ctx, 600, 23, BODY); ctx.fillStyle = C.text2; ctx.fillText(`  ·  ${p.faltantes} por cursar`, lx, yy);

        // Chips de precio e inicio
        const t = textosChips(ctx, p, conPrecio);
        if (t.precio || t.inicio) {
            yy += 26; let cxp = x0;
            if (t.precio) cxp += chip(ctx, cxp, yy, t.precio, C.pinkSoft, C.pink) + 12;
            if (t.inicio) {
                if (t.dosFilas) { cxp = x0; yy += 62; }
                chip(ctx, cxp, yy, t.inicio, C.greenSoft, C.green2);
            }
        }
    }

    async function generar({ titulo, programas, nombre, conPrecio, cfg }) {
        try { await Promise.all(['800 56px Outfit', '700 36px Outfit', '600 22px Inter', '700 22px Inter', '800 22px Inter'].map((f) => document.fonts.load(f))); } catch (e) { /* fuentes del sistema */ }
        const logo = await loadImg('/logo.jpg');
        const tmp = document.createElement('canvas').getContext('2d');

        // Medidas
        font(tmp, 800, 58, DISPLAY);
        const head = wrap(tmp, 'Tu título SENA te acerca a tu carrera profesional', W - PAD * 2, 2);
        font(tmp, 600, 27, BODY);
        const tit = wrap(tmp, titulo, W - PAD * 2 - 60, 2);
        const heroH = 210 + (nombre ? 46 : 0) + head.length * 66 + 30 + tit.length * 36 + 50 + 60;
        const medidas = programas.map((p) => medirPrograma(tmp, p, conPrecio));
        const ahorro = conPrecio ? Math.max(0, ...programas.map((p) => (p.precio && p.precio.ahorro_total) || 0)) : 0;
        let H = heroH + 40 + 50 + medidas.reduce((s, m) => s + m.h + 24, 0) + (ahorro ? 150 : 0) + 140 + 150;

        const cv = document.createElement('canvas'); cv.width = W; cv.height = H;
        const ctx = cv.getContext('2d');
        ctx.fillStyle = C.white; ctx.fillRect(0, 0, W, H);

        // ---- Encabezado
        const hg = ctx.createLinearGradient(0, 0, W, heroH); hg.addColorStop(0, '#8cc63f'); hg.addColorStop(1, '#3f6a17');
        ctx.fillStyle = hg; ctx.fillRect(0, 0, W, heroH);
        ctx.save(); ctx.globalAlpha = 0.12; ctx.fillStyle = C.white; ctx.beginPath(); ctx.arc(W - 90, 70, 260, 0, Math.PI * 2); ctx.fill();
        ctx.globalAlpha = 0.85; ctx.fillStyle = C.pink; ctx.beginPath(); ctx.arc(W + 20, heroH + 10, 150, 0, Math.PI * 2); ctx.fill(); ctx.restore();
        ctx.fillStyle = C.white; rr(ctx, PAD, 60, 100, 100, 26); ctx.fill();
        if (logo) ctx.drawImage(logo, PAD + 14, 74, 72, 72);
        ctx.fillStyle = C.white; font(ctx, 800, 44, DISPLAY); ctx.fillText('Areandina', PAD + 128, 108);
        ctx.globalAlpha = 0.85; font(ctx, 600, 22, BODY); ctx.fillText('Homologación para egresados SENA · 100% virtual', PAD + 128, 144); ctx.globalAlpha = 1;
        let y = 230;
        if (nombre) { font(ctx, 600, 30, BODY); ctx.globalAlpha = 0.95; ctx.fillText(`¡Hola, ${nombre}!`, PAD, y); ctx.globalAlpha = 1; y += 46; }
        font(ctx, 800, 58, DISPLAY); head.forEach((l) => { ctx.fillText(l, PAD, y + 50); y += 66; });
        y += 30;
        const pillH = tit.length * 36 + 40;
        ctx.fillStyle = 'rgba(255,255,255,0.18)'; rr(ctx, PAD, y, W - PAD * 2, pillH, 22); ctx.fill();
        ctx.fillStyle = C.white; font(ctx, 600, 18, BODY); ctx.globalAlpha = 0.8; ctx.fillText('TU TÍTULO', PAD + 30, y + 30); ctx.globalAlpha = 1;
        font(ctx, 700, 27, BODY); tit.forEach((l, i) => ctx.fillText(l, PAD + 30, y + 66 + i * 36));
        y = heroH + 40;

        // ---- Programas
        ctx.fillStyle = C.ink; font(ctx, 800, 34, DISPLAY);
        ctx.fillText(programas.length > 1 ? `Puedes homologar en ${programas.length} carreras` : 'Puedes homologar en esta carrera', PAD, y + 30);
        y += 60;
        programas.forEach((p, i) => { dibujarPrograma(ctx, p, y, medidas[i], conPrecio); y += medidas[i].h + 24; });

        // ---- Ahorro
        if (ahorro) {
            const ag = ctx.createLinearGradient(PAD, 0, W - PAD, 0); ag.addColorStop(0, C.pink); ag.addColorStop(1, '#ff4fa8');
            ctx.fillStyle = ag; rr(ctx, PAD, y + 6, W - PAD * 2, 120, 30); ctx.fill();
            ctx.fillStyle = C.white; font(ctx, 600, 23, BODY); ctx.fillText('Ahorro estimado frente a cursar la carrera completa', PAD + 36, y + 52);
            font(ctx, 800, 44, DISPLAY); ctx.fillText(`Hasta ${money(ahorro)}`, PAD + 36, y + 102);
            y += 150;
        }

        // ---- Beneficios
        const ben = ['Inscripción sin costo', 'Estudio de homologación sin costo', 'Clases en vivo después de las 6 p. m.'];
        const colW = (W - PAD * 2) / 3;
        ben.forEach((b, i) => {
            const bx = PAD + i * colW; check(ctx, bx + 24, y + 40, 22, C.green, C.white);
            ctx.fillStyle = C.ink; font(ctx, 700, 21, BODY);
            wrap(ctx, b, colW - 70, 2).forEach((l, j) => ctx.fillText(l, bx + 58, y + 34 + j * 26));
        });
        y += 110;

        // ---- Pie
        ctx.fillStyle = C.dark; ctx.fillRect(0, H - 150, W, 150);
        ctx.fillStyle = C.white; font(ctx, 800, 32, DISPLAY); ctx.fillText('¡Escríbeme y empieza tu carrera!', PAD, H - 86);
        ctx.globalAlpha = 0.7; font(ctx, 500, 20, BODY);
        const pie = [cfg && cfg.asesor ? `Tu asesor: ${cfg.asesor}` : 'Universidad Areandina', 'Valores por semestre', 'Cupos limitados'].join('  ·  ');
        ctx.fillText(pie, PAD, H - 48); ctx.globalAlpha = 1;
        ctx.fillStyle = C.green; ctx.fillRect(0, H - 150, W, 6);
        return cv;
    }

    window.ImagenHomologacion = { generar };
})();
