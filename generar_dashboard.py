#!/usr/bin/env python3
"""
Dashboard Talentos ZAS — Generador
====================================
Descarga datos de Odoo via JSON-RPC y genera un HTML auto-contenido.

Uso:
    python generar_dashboard.py

Salida:
    dashboard_talentos.html  (en esta misma carpeta)
"""

import os
import requests
from datetime import datetime
from collections import defaultdict

# ══════════════════════════════════════════════════════════════
# CONFIGURACIÓN
# ══════════════════════════════════════════════════════════════
ODOO_URL  = "https://zas-talent.odoo.com"
ODOO_DB   = "zas-talent"
ODOO_USER = "martina.boazzo@zastalents.com"
ODOO_PASS = os.environ.get("ODOO_PASS", "Fran4732")  # en GitHub Actions viene del secret

OUTPUT_FILE = "dashboard_talentos.html"

MEXICO_ID       = 3
ALL_COMPANY_IDS = [1, 2, 3, 4, 5, 6]
BATCH           = 500

PAIS_LABELS = {
    "Campañas":                  "Campañas Argentinas",
    "Campañas Argentinas":       "Campañas Argentinas",
    "campanas_argentinas":       "Campañas Argentinas",
    "arg":                       "Campañas Argentinas",
    "Campañas Chile":            "Campañas Chile",
    "Campañas Chilenas":         "Campañas Chile",
    "campanas_chile":            "Campañas Chile",
    "chi":                       "Campañas Chile",
    "Campañas Colombia":         "Campañas Colombia",
    "Campañas Colombianas":      "Campañas Colombia",
    "campanas_colombia":         "Campañas Colombia",
    "col":                       "Campañas Colombia",
    "US Campaigns":              "US Campaigns",
    "Campañas USA":              "US Campaigns",
    "usa":                       "US Campaigns",
    "us_campaigns":              "US Campaigns",
    "Campañas Perú":             "Campañas Perú",
    "Campañas Peru":             "Campañas Perú",
    "campanas_peru":             "Campañas Perú",
    "per":                       "Campañas Perú",
    "Campañas Internacionales":  "Campañas Internacionales",
    "campanas_internacionales":  "Campañas Internacionales",
    "int":                       "Campañas Internacionales",
}


def traducir_pais(val):
    if not val or val is False:
        return ""
    if isinstance(val, (list, tuple)):
        val = val[1] if len(val) > 1 else str(val[0])
    val = str(val).strip()
    if val in PAIS_LABELS:
        return PAIS_LABELS[val]
    val_lower = val.lower()
    for k, v in PAIS_LABELS.items():
        if k.lower() == val_lower:
            return v
    return val


def login(session):
    print("  Autenticando...")
    resp = session.post(f"{ODOO_URL}/web/session/authenticate", json={
        "jsonrpc": "2.0", "method": "call", "id": 1,
        "params": {"db": ODOO_DB, "login": ODOO_USER, "password": ODOO_PASS}
    }, timeout=30)
    resp.raise_for_status()
    result = resp.json().get("result", {})
    uid = result.get("uid")
    if not uid:
        raise RuntimeError(f"Login fallido — revisá usuario/password. Detalle: {result.get('error', result)}")
    print(f"  ✓ Login OK  (user_id={uid})")
    return uid


def activar_multicompany(session, uid):
    session.post(f"{ODOO_URL}/web/dataset/call_kw", json={
        "jsonrpc": "2.0", "method": "call", "id": 2,
        "params": {
            "model": "res.users", "method": "write",
            "args": [[uid], {"company_id": 1, "company_ids": [[6, False, ALL_COMPANY_IDS]]}],
            "kwargs": {"context": {"allowed_company_ids": ALL_COMPANY_IDS}}
        }
    }, timeout=30)
    print(f"  ✓ Multi-company activado: {ALL_COMPANY_IDS}")


def fetch_all(session, model, domain, fields, label=""):
    records, offset = [], 0
    while True:
        resp = session.post(f"{ODOO_URL}/web/dataset/call_kw", json={
            "jsonrpc": "2.0", "method": "call", "id": 99,
            "params": {
                "model": model, "method": "search_read", "args": [domain],
                "kwargs": {
                    "fields": fields, "limit": BATCH, "offset": offset,
                    "context": {"allowed_company_ids": ALL_COMPANY_IDS}
                }
            }
        }, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            raise RuntimeError(f"Error Odoo en {model}: {data['error']}")
        batch = data.get("result", [])
        if not batch:
            break
        records.extend(batch)
        if label:
            print(f"    {label}: {len(records)} ...", end="\r")
        offset += len(batch)
        if len(batch) < BATCH:
            break
    if label:
        print(f"    {label}: {len(records)}  ✓         ")
    return records


def bajar_datos():
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})

    uid = login(session)
    activar_multicompany(session, uid)

    print("\n[1/7] Productos (talentos)...")
    productos = fetch_all(
        session,
        model="product.template",
        domain=[["purchase_ok", "=", True], ["sale_ok", "=", True],
                ["name", "!=", "Booking Fees"]],
        fields=["id", "name", "company_id"],
        label="productos"
    )
    talent_names = sorted({p["name"] for p in productos if p.get("name") and p["name"] != "Booking Fees"})
    print(f"    → {len(talent_names)} talentos únicos")

    prod_template_by_name = {}
    for p in productos:
        prod_template_by_name.setdefault(p["name"], []).append(p["id"])

    print("\n[2/7] Subtareas...")
    subtareas = fetch_all(
        session,
        model="project.task",
        domain=[["parent_id", "!=", False], ["sale_order_id", "!=", False]],
        fields=["id", "name", "parent_id", "sale_order_id", "sale_line_id", "stage_id",
                "x_studio_fecha_de_publicacin", "x_studio_fecha_limite",
                "date_deadline", "company_id", "project_id"],
        label="subtareas"
    )

    so_ids = list({
        (t["sale_order_id"][0] if isinstance(t["sale_order_id"], list) else t["sale_order_id"])
        for t in subtareas if t.get("sale_order_id")
    })
    print(f"\n[3/7] {len(so_ids)} sale orders referenciados")

    print("\n[4/7] Sale orders...")
    so_raw = []
    for i in range(0, len(so_ids), 200):
        so_raw.extend(fetch_all(
            session,
            model="sale.order",
            domain=[["id", "in", so_ids[i:i+200]]],
            fields=["id", "name", "state", "company_id", "amount_total",
                    "amount_untaxed", "currency_id",
                    "x_studio_campaas", "x_studio_campaas_1",
                    "x_studio_bu", "x_studio_bu_1",
                    "x_studio_tipo_de_contrato", "x_studio_nombre_de_la_campaa",
                    "x_studio_marca", "date_order", "partner_id",
                    "invoice_ids", "order_line",
                    "x_studio_factura_o_boleta", "x_studio_selection_field_4kh_1it0ckuc4",
                    "payment_term_id"],
        ))

    sale_orders = [
        so for so in so_raw
        if (so.get("company_id") and
            (so["company_id"][0] if isinstance(so["company_id"], list) else so["company_id"]) != MEXICO_ID)
        and so.get("state") in ("sale", "done")
    ]
    print(f"    {len(so_raw)} raw → {len(sale_orders)} válidos  ✓")
    so_map = {so["id"]: so for so in sale_orders}

    subtareas = [
        t for t in subtareas
        if so_map.get(t["sale_order_id"][0] if isinstance(t["sale_order_id"], list) else t["sale_order_id"])
    ]

    print("\n[5/7] Líneas de venta...")
    sol_ids_all = list({lid for so in sale_orders for lid in (so.get("order_line") or [])})
    sol_map = {}
    for i in range(0, len(sol_ids_all), 200):
        lines = fetch_all(
            session,
            model="sale.order.line",
            domain=[["id", "in", sol_ids_all[i:i+200]]],
            fields=["id", "order_id", "product_id", "task_id", "price_subtotal"],
        )
        for line in lines:
            prod_name = ""
            if line.get("product_id"):
                prod_name = line["product_id"][1] if isinstance(line["product_id"], list) else ""
            sol_map[line["id"]] = {
                "talent": _extract_talent_from_product(prod_name),
                "amount": line.get("price_subtotal") or 0,
            }

    task_talent_map = {}
    task_amount_map = {}
    for t in subtareas:
        if t.get("sale_line_id"):
            sol_id = t["sale_line_id"][0] if isinstance(t["sale_line_id"], list) else t["sale_line_id"]
            if sol_id in sol_map:
                task_talent_map[t["id"]] = sol_map[sol_id]["talent"]
                task_amount_map[t["id"]] = sol_map[sol_id]["amount"]
    for t in subtareas:
        if t["id"] not in task_talent_map:
            task_talent_map[t["id"]] = _extract_talent_from_task(t.get("name", ""))

    print(f"    {len(sol_ids_all)} líneas procesadas  ✓")

    print("\n[6/7] Facturas de cliente...")
    inv_ids = list({inv_id for so in sale_orders for inv_id in (so.get("invoice_ids") or [])})
    client_invoices_map = defaultdict(list)
    if inv_ids:
        cinvs_raw = []
        for i in range(0, len(inv_ids), 200):
            cinvs_raw.extend(fetch_all(
                session, model="account.move",
                domain=[["id", "in", inv_ids[i:i+200]]],
                fields=["id", "name", "move_type", "state", "payment_state",
                        "invoice_date_due", "amount_untaxed", "amount_total", "currency_id"],
            ))
        inv_by_id = {i["id"]: i for i in cinvs_raw}
        for so in sale_orders:
            for inv_id in (so.get("invoice_ids") or []):
                inv = inv_by_id.get(inv_id)
                if inv and inv["move_type"] in ("out_invoice", "out_refund") and inv["state"] != "cancel":
                    client_invoices_map[so["id"]].append(inv)
        print(f"    {len(inv_ids)} facturas  ✓")
    else:
        print("    Sin facturas")

    print("\n[7/7] OC y facturas proveedor...")
    so_names = [so["name"] for so in sale_orders]
    po_map = {}
    pos_raw = []
    if so_names:
        for i in range(0, len(so_names), 200):
            pos_raw.extend(fetch_all(
                session, model="purchase.order",
                domain=[["origin", "in", so_names[i:i+200]]],
                fields=["id", "name", "origin", "state", "amount_untaxed", "invoice_ids"],
            ))
        for po in pos_raw:
            if po.get("origin"):
                po_map[po["origin"]] = po

    vendor_invoices_map = defaultdict(list)
    po_inv_ids = list({inv_id for po in pos_raw for inv_id in (po.get("invoice_ids") or [])})
    if po_inv_ids:
        vinvs_raw = []
        for i in range(0, len(po_inv_ids), 200):
            vinvs_raw.extend(fetch_all(
                session, model="account.move",
                domain=[["id", "in", po_inv_ids[i:i+200]]],
                fields=["id", "name", "move_type", "state", "payment_state",
                        "invoice_date_due", "amount_untaxed", "amount_total", "currency_id"],
            ))
        vinv_by_id = {v["id"]: v for v in vinvs_raw}
        for po in pos_raw:
            for inv_id in (po.get("invoice_ids") or []):
                vinv = vinv_by_id.get(inv_id)
                if vinv and vinv["move_type"] == "in_invoice" and vinv["state"] != "cancel":
                    vendor_invoices_map[po["id"]].append(vinv)
    print(f"    {len(pos_raw)} OC, {len(po_inv_ids)} fact. proveedor  ✓")

    return talent_names, subtareas, task_talent_map, task_amount_map, so_map, client_invoices_map, po_map, vendor_invoices_map


def _normalizar_nombre(nombre):
    if not nombre:
        return "Sin nombre"
    return nombre.strip().title()


def _extract_talent_from_product(prod_name):
    if not prod_name:
        return "Sin nombre"
    idx = prod_name.find("(")
    raw = prod_name[:idx].strip() if idx > 0 else prod_name.strip()
    return _normalizar_nombre(raw)


def _extract_talent_from_task(task_name):
    if not task_name:
        return "Sin nombre"
    idx = task_name.find("(")
    raw = task_name[:idx].strip() if idx > 0 else task_name.strip()
    return _normalizar_nombre(raw)


def pais_final(so):
    if not so:
        return ""
    c1 = traducir_pais(so.get("x_studio_campaas"))
    c2 = traducir_pais(so.get("x_studio_campaas_1"))
    if c1 and c2 and c1 != c2:
        return f"{c1} / {c2}"
    return c1 or c2 or ""


def get_currency(so):
    if not so or not so.get("currency_id"):
        return "USD"
    v = so["currency_id"]
    return v[1] if isinstance(v, (list, tuple)) else str(v)


def get_marca(so):
    if not so:
        return "—"
    v = so.get("x_studio_marca")
    if not v or v is False:
        return "—"
    return v[1] if isinstance(v, (list, tuple)) else str(v)


def get_factura_boleta(so):
    def ex(v):
        if not v or v is False:
            return ""
        if isinstance(v, (list, tuple)):
            return str(v[1] if len(v) > 1 else v[0]).strip()
        return str(v).strip()
    f1 = ex(so.get("x_studio_factura_o_boleta"))
    f2 = ex(so.get("x_studio_selection_field_4kh_1it0ckuc4"))
    partes = [p for p in [f1, f2] if p]
    return " / ".join(partes) if partes else ""


def get_nums_facturas_prov(vinvs):
    nums = [v.get("name", "") for v in vinvs if v.get("name")]
    return ", ".join(nums) if nums else ""


def get_campana(so):
    if not so:
        return "—"
    v = so.get("x_studio_nombre_de_la_campaa")
    if not v or v is False:
        return so.get("name", "—")
    return str(v)


def fmt_date(d):
    if not d or d is False:
        return None
    try:
        return datetime.fromisoformat(str(d)[:10]).strftime("%d/%m/%Y")
    except Exception:
        return str(d)


def fmt_num(n):
    if n is None:
        return "—"
    try:
        return f"{float(n):,.0f}".replace(",", ".")
    except Exception:
        return str(n)


def fmt_pct(numerator, denominator):
    try:
        if not denominator or float(denominator) == 0:
            return "—"
        pct = (float(numerator) / float(denominator)) * 100
        return f"{pct:.1f}%"
    except Exception:
        return "—"


def month_key(date_str):
    try:
        dt = datetime.fromisoformat(str(date_str)[:10])
        return (dt.strftime("%Y-%m"), dt.strftime("%B %Y").capitalize())
    except Exception:
        return ("9999-99", "Sin fecha")


def badge(cls, text):
    return f'<span class="badge {cls}">{text}</span>'


def get_payment_term(so):
    if not so:
        return "—"
    v = so.get("payment_term_id")
    if not v or v is False:
        return "—"
    return v[1] if isinstance(v, (list, tuple)) else str(v)


def construir_datos(talent_names, subtareas, task_talent_map, task_amount_map, so_map,
                    client_inv_map, po_map, vendor_inv_map):
    talent_tasks = defaultdict(list)
    for t in subtareas:
        talent = task_talent_map.get(t["id"], _extract_talent_from_task(t.get("name", "")))
        talent_tasks[talent].append(t)

    talentos = {}
    all_talents = sorted(set(talent_tasks.keys()) | set(talent_names))

    for talent_name in all_talents:
        tasks = talent_tasks.get(talent_name, [])
        if not tasks:
            continue

        published, pending, so_ids_seen = [], [], set()

        for t in tasks:
            oid = t["sale_order_id"][0] if isinstance(t["sale_order_id"], list) else t["sale_order_id"]
            so = so_map.get(oid)
            if not so:
                continue
            so_ids_seen.add(so["id"])
            amt = task_amount_map.get(t["id"])  # price_subtotal unitario de la línea
            fecha_pub = t.get("x_studio_fecha_de_publicacin")
            if fecha_pub and fecha_pub is not False:
                published.append({"task": t, "so": so, "amount": amt})
            else:
                pending.append({"task": t, "so": so, "amount": amt})

        finance = []
        for so_id in so_ids_seen:
            so   = so_map[so_id]
            neto = so.get("amount_untaxed") or 0
            cur  = get_currency(so)

            cinvs    = client_inv_map.get(so_id, [])
            facturas = [i for i in cinvs if i.get("move_type") == "out_invoice"]
            notas_cr = [i for i in cinvs if i.get("move_type") == "out_refund"]
            tot_fact = (sum(i.get("amount_untaxed") or 0 for i in facturas)
                        - sum(i.get("amount_untaxed") or 0 for i in notas_cr))
            all_paid = bool(facturas) and all(
                i.get("payment_state") in ("paid", "in_payment") for i in facturas
            )

            # ── MEJORA 2: si la venta está 100% pagada (factura consolidada),
            #    forzar pct_fact=100 aunque tot_fact > neto ──────────────────
            if neto > 0:
                pct_fact_raw = (tot_fact / neto) * 100
            else:
                pct_fact_raw = 0

            if all_paid and pct_fact_raw > 100:
                pct_fact = 100
            else:
                pct_fact = round(pct_fact_raw)

            is_100 = bool(facturas) and pct_fact >= 100

            dues        = sorted(i["invoice_date_due"] for i in facturas if i.get("invoice_date_due"))
            vencimiento = fmt_date(dues[-1]) if dues else None

            if not facturas:
                factura_status = "pendiente_factura"
                cobro_status, cobro_fecha = None, None
            elif is_100:
                factura_status = "100"
                cobro_status   = "cobrado" if all_paid else "pendiente_cobro"
                cobro_fecha    = vencimiento if all_paid else None
            else:
                factura_status = f"{pct_fact}%"
                cobro_status, cobro_fecha = None, None

            po       = po_map.get(so["name"])
            v_neto   = None
            v_status = None
            v_fecha  = None
            v_nums   = ""
            if po:
                vinvs = vendor_inv_map.get(po["id"], [])
                if vinvs:
                    v_neto   = sum(i.get("amount_untaxed") or 0 for i in vinvs)
                    v_paid   = all(i.get("payment_state") in ("paid", "in_payment") for i in vinvs)
                    v_dues   = sorted(i["invoice_date_due"] for i in vinvs if i.get("invoice_date_due"))
                    v_fecha  = fmt_date(v_dues[-1]) if v_dues else None
                    v_status = "pagado" if v_paid else "pendiente"
                    v_nums   = get_nums_facturas_prov(vinvs)
                else:
                    v_status = "sin_factura"

            pct_talento  = fmt_pct(v_neto, neto) if v_neto is not None else "—"
            fact_boleta  = get_factura_boleta(so)

            finance.append({
                "so": so, "neto": neto, "cur": cur,
                "factura_status": factura_status, "pct_fact": pct_fact,
                "vencimiento": vencimiento,
                "cobro_status": cobro_status, "cobro_fecha": cobro_fecha,
                "tiene_po": po is not None,
                "v_neto": v_neto, "v_status": v_status, "v_fecha": v_fecha,
                "v_nums": v_nums,
                "pct_talento": pct_talento,
                "fact_boleta": fact_boleta,
                "pais": pais_final(so),
                "payment_term": get_payment_term(so),
            })

        finance.sort(key=lambda x: x["so"].get("name", ""))
        # Índice rápido por nombre de venta para uso en render_published / render_pending
        finance_by_so = {f["so"]["name"]: f for f in finance}
        talentos[talent_name] = {
            "published":    published,
            "pending":      pending,
            "finance":      finance,
            "finance_by_so": finance_by_so,
        }

    return talentos


def _render_fact_cobro_cell(f):
    """Genera el HTML para la celda Factura / Cobro en publicados/pendientes."""
    if f is None:
        return badge("bd", "—")
    fs = f["factura_status"]
    cs = f["cobro_status"]
    venc = f.get("vencimiento")

    if fs == "pendiente_factura":
        fact_part  = badge("by", "Pendiente factura")
        cobro_part = badge("bd", "—")
    elif fs == "100":
        fact_part = badge("bg", "✓ 100%")
        if cs == "cobrado":
            cobro_part = f'<span class="badge bg">{f["cobro_fecha"] or "Cobrado"}</span>'
        elif cs == "pendiente_cobro":
            venc_txt = f" · vto. {venc}" if venc else ""
            cobro_part = badge("by", f"Pendiente cobro{venc_txt}")
        else:
            cobro_part = badge("bd", "—")
    else:
        fact_part  = badge("by", f"{fs} facturado")
        cobro_part = badge("bd", "—")

    return f'<div class="fc-cell">{fact_part}<span class="fc-sep">/</span>{cobro_part}</div>'


def _render_pago_talento_cell(f):
    """Genera el HTML para la celda Pago talento en publicados/pendientes."""
    if f is None:
        return badge("bd", "—")
    if not f["tiene_po"]:
        return badge("bd", "Sin OC")
    vs = f["v_status"]
    if vs == "sin_factura":
        return badge("bd", "Sin fact. prov.")
    elif vs == "pagado":
        return f'<span class="badge bg">{f["v_fecha"] or "Pagado"}</span>'
    elif vs == "pendiente":
        return badge("br", "Pendiente pago")
    return badge("bd", "—")


def render_published(published, finance_by_so=None):
    if not published:
        return '<div class="empty-msg"><span class="icon">📭</span>Sin contenidos publicados</div>'

    fbs = finance_by_so or {}

    by_month = defaultdict(list)
    for item in published:
        mk, ml = month_key(item["task"]["x_studio_fecha_de_publicacin"])
        by_month[(mk, ml)].append(item)

    html = ""
    for i, ((mk, ml), items) in enumerate(sorted(by_month.items(), key=lambda x: x[0][0], reverse=True)):
        gid  = f"mg-{mk}-{i}"
        tots = defaultdict(float)
        for it in items:
            tots[get_currency(it["so"])] += it["amount"] if it.get("amount") is not None else (it["so"].get("amount_untaxed") or 0)
        tot_str = "  ·  ".join(f"{c} {fmt_num(v)}" for c, v in tots.items())

        rows = ""
        for it in items:
            t, so = it["task"], it["so"]
            son   = t["sale_order_id"][1] if isinstance(t["sale_order_id"], list) else str(t["sale_order_id"])
            pais  = pais_final(so)
            f_dat = fbs.get(so["name"])
            neto_unit = it["amount"] if it.get("amount") is not None else so.get("amount_untaxed")
            pt = f_dat["payment_term"] if f_dat else "—"
            rows += f"""<tr>
              <td><span class="num">{son}</span></td>
              <td><span class="tnc">{t.get("name","—")}</span></td>
              <td><span class="sm">{get_marca(so)}</span></td>
              <td><span class="sm">{get_campana(so)}</span></td>
              <td>{badge("bd", get_currency(so))}</td>
              <td class="amt">{fmt_num(neto_unit)}</td>
              <td><span class="dv">{fmt_date(t["x_studio_fecha_de_publicacin"]) or "—"}</span></td>
              <td><span class="pt">{pais or "—"}</span></td>
              <td>{_render_fact_cobro_cell(f_dat)}</td>
              <td>{_render_pago_talento_cell(f_dat)}</td>
              <td><span class="sm">{pt}</span></td>
            </tr>"""

        html += f"""
        <div class="mg" id="{gid}">
          <div class="mh" onclick="tog('{gid}')">
            <div class="mt">{ml.capitalize()} {badge("bd", f"{len(items)} cont.")}</div>
            <div class="ms">{tot_str} <span class="chv">▾</span></div>
          </div>
          <div class="mb"><div class="tw"><table>
            <thead><tr>
              <th>N° Venta</th><th>Contenido</th><th>Marca</th><th>Campaña</th>
              <th>Moneda</th><th class="r">Neto</th><th>Publicación</th><th>País campaña</th>
              <th>Fact. / Cobro</th><th>Pago talento</th><th>Plazo de pago</th>
            </tr></thead>
            <tbody>{rows}</tbody>
          </table></div></div>
        </div>"""
    return html


def render_pending(pending, finance_by_so=None):
    if not pending:
        return '<div class="empty-msg"><span class="icon">✅</span>Sin contenidos pendientes</div>'

    fbs = finance_by_so or {}

    rows = ""
    for it in pending:
        t, so = it["task"], it["so"]
        son  = t["sale_order_id"][1] if isinstance(t["sale_order_id"], list) else str(t["sale_order_id"])
        est  = t.get("x_studio_fecha_limite") or t.get("date_deadline")
        est_html = f'<span class="de">{fmt_date(est)}</span>' if (est and est is not False) else badge("bd", "Sin fecha")
        pais  = pais_final(so)
        f_dat = fbs.get(so["name"])
        neto_unit = it["amount"] if it.get("amount") is not None else so.get("amount_untaxed")
        pt = f_dat["payment_term"] if f_dat else "—"
        rows += f"""<tr>
          <td><span class="num">{son}</span></td>
          <td><span class="tnc">{t.get("name","—")}</span></td>
          <td><span class="sm">{get_marca(so)}</span></td>
          <td><span class="sm">{get_campana(so)}</span></td>
          <td>{badge("bd", get_currency(so))}</td>
          <td class="amt">{fmt_num(neto_unit)}</td>
          <td>{est_html}</td>
          <td><span class="pt">{pais or "—"}</span></td>
          <td>{_render_fact_cobro_cell(f_dat)}</td>
          <td>{_render_pago_talento_cell(f_dat)}</td>
          <td><span class="sm">{pt}</span></td>
        </tr>"""

    return f"""<div class="tw"><table>
      <thead><tr>
        <th>N° Venta</th><th>Contenido</th><th>Marca</th><th>Campaña</th>
        <th>Moneda</th><th class="r">Neto</th><th>Fecha estimada</th><th>País campaña</th>
        <th>Fact. / Cobro</th><th>Pago talento</th><th>Plazo de pago</th>
      </tr></thead>
      <tbody>{rows}</tbody>
    </table></div>"""


def render_finance(finance):
    if not finance:
        return '<div class="empty-msg"><span class="icon">📋</span>Sin ventas</div>'

    tots = defaultdict(float)
    for f in finance:
        tots[f["cur"]] += f["neto"]

    summary = '<div class="ss">'
    for c, v in tots.items():
        cnt = sum(1 for f in finance if f["cur"] == c)
        summary += f'<div class="sc"><div class="sl">Neto {c}</div><div class="sv">{fmt_num(v)}</div><div class="sb">{cnt} ventas</div></div>'
    summary += '</div>'

    rows = ""
    for f in finance:
        so = f["so"]

        fs = f["factura_status"]
        fact_h = (badge("by", "Pendiente factura") if fs == "pendiente_factura"
                  else badge("bg", "✓ 100%") if fs == "100"
                  else badge("by", f"{fs} facturado"))

        venc_h  = (f'<span class="dv">{f["vencimiento"]}</span>' if f["vencimiento"]
                   else badge("bd", "—"))

        cs = f["cobro_status"]
        cobro_h = (f'<span class="badge bg">{f["cobro_fecha"] or "Cobrado"}</span>' if cs == "cobrado"
                   else badge("by", "Pendiente cobro") if cs == "pendiente_cobro"
                   else badge("bd", "—"))

        if not f["tiene_po"]:
            np_h   = badge("bd", "Sin OC")
            pago_h = badge("bd", "—")
        else:
            vs = f["v_status"]
            np_h = (badge("bd", "Sin fact. prov.") if vs == "sin_factura"
                    else f'<span class="mf"><span class="ct">{f["cur"]}</span>{fmt_num(f["v_neto"])}</span>')
            pago_h = (f'<span class="badge bg">{f["v_fecha"] or "Pagado"}</span>' if vs == "pagado"
                      else badge("br", "Pendiente pago") if vs == "pendiente"
                      else badge("bd", "—"))

        pct_h = f'<span class="pct">{f["pct_talento"]}</span>' if f["pct_talento"] != "—" else badge("bd", "—")

        fb_h  = f'<span class="sm">{f["fact_boleta"]}</span>' if f["fact_boleta"] else badge("bd", "—")
        vn_h  = f'<span class="sm">{f["v_nums"]}</span>' if f.get("v_nums") else badge("bd", "—")

        campana_txt = get_campana(so)
        campana_esc = campana_txt.replace('"', '&quot;')
        campana_h   = f'<span class="sm" title="{campana_esc}">{campana_txt}</span>'

        pais_txt = f["pais"] or "—"
        pais_h   = f'<span class="pt">{pais_txt}</span>'

        # data-v para "Fact. cliente": almacenar el pct_fact numérico para filtro condicional
        fact_data_v = str(f["pct_fact"]) if fs not in ("pendiente_factura",) else "pendiente_factura"
        payment_term = f["payment_term"]

        rows += f"""<tr>
          <td data-v="{so["name"]}"><span class="num">{so["name"]}</span></td>
          <td data-v="{get_marca(so)}"><span class="sm">{get_marca(so)}</span></td>
          <td data-v="{campana_txt}">{campana_h}</td>
          <td data-v="{f["cur"]}">{badge("bd", f["cur"])}</td>
          <td class="amt" data-v="{f["neto"]}">{fmt_num(f["neto"])}</td>
          <td data-v="{f["fact_boleta"]}">{fb_h}</td>
          <td data-v="{fact_data_v}">{fact_h}</td>
          <td data-v="{f["vencimiento"] or ""}">{venc_h}</td>
          <td data-v="{f["cobro_status"] or ""}">{cobro_h}</td>
          <td class="amt" data-v="{f["v_neto"] or 0}">{np_h}</td>
          <td data-v="{f.get("v_nums","")}">{vn_h}</td>
          <td class="amt" data-v="{f["pct_talento"]}">{pct_h}</td>
          <td data-v="{f["v_status"] or ""}">{pago_h}</td>
          <td data-v="{pais_txt}">{pais_h}</td>
          <td data-v="{payment_term}">{payment_term}</td>
        </tr>"""

    # ── MEJORA 1: filtro condicional para Fact. cliente ──────────────────────
    table = f"""<div class="tw">
      <div class="fbar" id="fbar">
        <span class="flab">Filtrar:</span>
        <div class="fsel-wrap">
          <label class="fsel-lbl">N° Venta</label>
          <input class="fsel ftext" type="text" data-col="0" placeholder="Buscar..."
                 oninput="applyFinFilter(this.closest('.tw'))">
        </div>
        <div class="fsel-wrap">
          <label class="fsel-lbl">Marca</label>
          <select class="fsel" data-col="1" onchange="applyFinFilter(this.closest('.tw'))">
            <option value="">Todas</option>
          </select>
        </div>
        <div class="fsel-wrap">
          <label class="fsel-lbl">Campaña</label>
          <select class="fsel" data-col="2" onchange="applyFinFilter(this.closest('.tw'))">
            <option value="">Todas</option>
          </select>
        </div>
        <div class="fsel-wrap">
          <label class="fsel-lbl">Moneda</label>
          <select class="fsel" data-col="3" onchange="applyFinFilter(this.closest('.tw'))">
            <option value="">Todas</option>
          </select>
        </div>
        <div class="fsel-wrap">
          <label class="fsel-lbl">Fact/Boleta</label>
          <select class="fsel" data-col="5" onchange="applyFinFilter(this.closest('.tw'))">
            <option value="">Todas</option>
          </select>
        </div>
        <div class="fsel-wrap fsel-wrap-pct">
          <label class="fsel-lbl">Fact. cliente</label>
          <div class="pct-filter-row">
            <select class="fsel fsel-op" data-col="6" onchange="applyFinFilter(this.closest('.tw'))">
              <option value="">Sin filtro</option>
              <option value="lt">&lt; menor a</option>
              <option value="lte">&le; menor o igual</option>
              <option value="eq">= igual a</option>
              <option value="gte">&ge; mayor o igual</option>
              <option value="gt">&gt; mayor a</option>
              <option value="pendiente">Sin factura</option>
            </select>
            <input class="fsel-num" type="number" min="0" max="200" placeholder="%" 
                   oninput="applyFinFilter(this.closest('.tw'))" style="display:none">
          </div>
        </div>
        <div class="fsel-wrap">
          <label class="fsel-lbl">Vencimiento</label>
          <select class="fsel" data-col="7" onchange="applyFinFilter(this.closest('.tw'))">
            <option value="">Todos</option>
          </select>
        </div>
        <div class="fsel-wrap">
          <label class="fsel-lbl">Cobro</label>
          <select class="fsel" data-col="8" onchange="applyFinFilter(this.closest('.tw'))">
            <option value="">Todas</option>
          </select>
        </div>
        <div class="fsel-wrap">
          <label class="fsel-lbl">Pago talento</label>
          <select class="fsel" data-col="12" onchange="applyFinFilter(this.closest('.tw'))">
            <option value="">Todas</option>
          </select>
        </div>
        <div class="fsel-wrap">
          <label class="fsel-lbl">País campaña</label>
          <select class="fsel" data-col="13" onchange="applyFinFilter(this.closest('.tw'))">
            <option value="">Todos</option>
          </select>
        </div>
        <div class="fsel-wrap">
          <label class="fsel-lbl">Plazo de pago</label>
          <select class="fsel" data-col="14" onchange="applyFinFilter(this.closest('.tw'))">
            <option value="">Todos</option>
          </select>
        </div>
        <button class="fclr" onclick="clearFinFilters(this.closest('.tw'))">✕ Limpiar</button>
      </div>
      <table>
      <thead><tr>
        <th>N° Venta</th><th>Marca</th><th>Campaña</th><th>Moneda</th>
        <th class="r">Neto</th><th>Fact/Boleta</th><th>Fact. cliente</th><th>Vencimiento</th>
        <th>Cobro 100%</th><th class="r">Fact. proveedor</th>
        <th>N° Fact. prov.</th><th class="r">% Talento</th><th>Pago talento</th><th>País campaña</th><th>Plazo de pago</th>
      </tr></thead>
      <tbody>{rows}</tbody>
    </table></div>"""

    return summary + table


CSS = r"""
:root{
  --bg:#0B0D13;--sf:#13161F;--sf2:#1C2030;--br:#252A3A;--br2:#303650;
  --ac:#4DFFC3;--tx:#E4E8F4;--mu:#7A819A;--di:#404560;
  --gn:#2ECC71;--gnb:rgba(46,204,113,.1);
  --yw:#F0B429;--ywb:rgba(240,180,41,.1);
  --rd:#FF4D6A;--rdb:rgba(255,77,106,.1);
  --mo:'IBM Plex Mono',monospace;--sa:'IBM Plex Sans',sans-serif;
}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--tx);font-family:var(--sa);font-size:13px;min-height:100vh}
.hdr{padding:24px 32px 18px;border-bottom:1px solid var(--br);display:flex;align-items:center;justify-content:space-between}
.lm{width:34px;height:34px;background:var(--ac);border-radius:6px;display:flex;align-items:center;justify-content:center;font-family:var(--mo);font-size:12px;color:#0B0D13;font-weight:600}
.lo{display:flex;align-items:center;gap:12px}
.lt{font-size:15px;font-weight:600;letter-spacing:-.3px}
.ls{font-size:10px;color:var(--mu);font-family:var(--mo);letter-spacing:.8px}
.lu{font-family:var(--mo);font-size:11px;color:var(--di)}
.ts{padding:16px 32px;border-bottom:1px solid var(--br)}
.tl{font-size:10px;font-family:var(--mo);letter-spacing:1.2px;color:var(--mu);text-transform:uppercase;margin-bottom:10px}
.sw{position:relative;max-width:280px;margin-bottom:10px}
.sw input{width:100%;background:var(--sf);border:1px solid var(--br2);color:var(--tx);padding:7px 10px 7px 30px;border-radius:7px;font-size:12px;font-family:var(--sa);outline:none;transition:.15s}
.sw input:focus{border-color:var(--ac)}
.sw svg{position:absolute;left:9px;top:50%;transform:translateY(-50%);color:var(--mu)}
.pills{display:flex;flex-wrap:wrap;gap:7px}
.pill{background:var(--sf);border:1px solid var(--br2);color:var(--mu);padding:5px 13px;border-radius:20px;cursor:pointer;font-size:12px;font-weight:500;transition:.15s;white-space:nowrap}
.pill:hover{border-color:var(--ac);color:var(--ac)}
.pill.active{background:rgba(77,255,195,.07);border-color:var(--ac);color:var(--ac)}
.tbar{padding:0 32px;border-bottom:1px solid var(--br);display:flex}
.tb{background:transparent;border:none;border-bottom:2px solid transparent;color:var(--mu);padding:12px 18px;cursor:pointer;font-size:13px;font-family:var(--sa);font-weight:500;transition:.15s;display:flex;align-items:center;gap:7px;margin-bottom:-1px}
.tb:hover{color:var(--tx)}.tb.active{color:var(--ac);border-bottom-color:var(--ac)}
.tc{background:var(--sf2);border-radius:10px;padding:1px 7px;font-size:10px;font-family:var(--mo)}
.main{padding:20px 32px}
.panel{display:none}.panel.active{display:block}
.ns{display:flex;flex-direction:column;align-items:center;padding:50px 0;gap:12px;color:var(--di)}
.ns .ar{font-size:22px;animation:bn 1.8s ease-in-out infinite}
@keyframes bn{0%,100%{transform:translateY(0)}50%{transform:translateY(-7px)}}
.empty-msg{display:flex;align-items:center;justify-content:center;padding:44px 0;gap:10px;color:var(--di);font-size:13px}
.empty-msg .icon{font-size:22px;opacity:.4}
.mg{margin-bottom:10px;border:1px solid var(--br);border-radius:9px;overflow:hidden}
.mh{padding:10px 16px;background:var(--sf);display:flex;align-items:center;justify-content:space-between;cursor:pointer;user-select:none;transition:.15s}
.mh:hover{background:var(--sf2)}
.mt{font-weight:600;font-size:13px;display:flex;align-items:center;gap:8px}
.ms{display:flex;gap:12px;align-items:center;font-family:var(--mo);font-size:11px;color:var(--mu)}
.chv{transition:.2s;font-size:11px;color:var(--mu)}
.mg.cl .chv{transform:rotate(-90deg)}
.mb{border-top:1px solid var(--br)}
.mg.cl .mb{display:none}
.tw{overflow-x:auto}
table{width:100%;border-collapse:collapse}
th{text-align:left;padding:9px 13px;font-size:10px;font-family:var(--mo);letter-spacing:.7px;color:var(--mu);text-transform:uppercase;border-bottom:1px solid var(--br);white-space:nowrap;background:var(--sf)}
th.r{text-align:right}
td{padding:10px 13px;border-bottom:1px solid var(--br);vertical-align:middle;white-space:nowrap}
tr:last-child td{border-bottom:none}
tr:hover td{background:rgba(255,255,255,.015)}
.num{font-family:var(--mo);font-size:12px;color:var(--ac);font-weight:500}
.tnc{font-weight:500;max-width:200px;overflow:hidden;text-overflow:ellipsis;display:block}
.sm{color:var(--mu);font-size:12px;max-width:140px;overflow:hidden;text-overflow:ellipsis;display:block}
.amt{font-family:var(--mo);font-size:12px;text-align:right}
.pt{display:inline-block;background:var(--sf2);border:1px solid var(--br2);border-radius:4px;padding:2px 7px;font-size:10px;font-family:var(--mo);color:var(--mu)}
.dv{font-family:var(--mo);font-size:12px}
.de{font-family:var(--mo);font-size:12px;color:var(--yw)}
.mf{font-family:var(--mo);font-size:12px}
.ct{font-size:10px;color:var(--mu);margin-right:3px}
.pct{font-family:var(--mo);font-size:12px;color:var(--ac)}
.badge{display:inline-flex;align-items:center;padding:3px 8px;border-radius:4px;font-size:11px;font-family:var(--mo);font-weight:500}
.bg{background:var(--gnb);color:var(--gn)}
.by{background:var(--ywb);color:var(--yw)}
.br{background:var(--rdb);color:var(--rd)}
.bd{background:var(--sf2);color:var(--di)}
.ss{display:flex;gap:10px;margin-bottom:16px;flex-wrap:wrap}
.sc{background:var(--sf);border:1px solid var(--br);border-radius:8px;padding:12px 18px;min-width:150px;flex:1}
.sl{font-size:10px;font-family:var(--mo);color:var(--mu);letter-spacing:.7px;text-transform:uppercase;margin-bottom:5px}
.sv{font-size:19px;font-weight:600;font-family:var(--mo);color:var(--ac)}
.sb{font-size:11px;color:var(--mu);margin-top:2px}
::-webkit-scrollbar{width:5px;height:5px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:var(--br2);border-radius:3px}
/* ── DROPDOWN ── */
.dd-wrap{position:relative;max-width:320px}
.dd-trigger{display:flex;align-items:center;justify-content:space-between;background:var(--sf);border:1px solid var(--br2);border-radius:8px;padding:8px 12px;cursor:pointer;transition:.15s;gap:10px}
.dd-trigger:hover{border-color:var(--ac)}
.dd-trigger.open{border-color:var(--ac);border-bottom-left-radius:0;border-bottom-right-radius:0}
.dd-selected{font-size:13px;color:var(--tx);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;flex:1}
.dd-selected.placeholder{color:var(--mu)}
.dd-arrow{color:var(--mu);font-size:11px;transition:.2s;flex-shrink:0}
.dd-list{display:none;position:absolute;top:100%;left:0;right:0;background:var(--sf);border:1px solid var(--ac);border-top:none;border-bottom-left-radius:8px;border-bottom-right-radius:8px;z-index:100;max-height:320px;overflow:hidden;flex-direction:column}
.dd-list.open-list{display:flex}
.dd-search{padding:8px 10px;border-bottom:1px solid var(--br)}
.dd-search input{width:100%;background:var(--sf2);border:1px solid var(--br2);color:var(--tx);padding:6px 10px;border-radius:6px;font-size:12px;font-family:var(--sa);outline:none}
.dd-search input:focus{border-color:var(--ac)}
.dd-items{overflow-y:auto;max-height:260px}
.dd-item{padding:8px 14px;font-size:12px;color:var(--mu);cursor:pointer;transition:.1s;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.dd-item:hover{background:var(--sf2);color:var(--ac)}
.dd-item.selected{color:var(--ac);background:rgba(77,255,195,.05)}
/* ── FILTROS FINANZAS ── */
.fbar{display:flex;align-items:center;flex-wrap:wrap;gap:10px;padding:10px 14px;background:var(--sf2);border-bottom:1px solid var(--br)}
.flab{font-size:10px;font-family:var(--mo);letter-spacing:.7px;color:var(--mu);text-transform:uppercase;margin-right:2px}
.fsel-wrap{display:flex;flex-direction:column;gap:3px}
.fsel-lbl{font-size:10px;font-family:var(--mo);color:var(--di);letter-spacing:.5px}
.fsel{background:var(--sf);border:1px solid var(--br2);color:var(--tx);padding:5px 10px;border-radius:6px;font-size:12px;font-family:var(--sa);outline:none;cursor:pointer;transition:.15s}
.ftext{cursor:text;min-width:90px}
.fsel:focus,.fsel:hover{border-color:var(--ac)}
.fclr{background:transparent;border:1px solid var(--br2);color:var(--mu);padding:5px 12px;border-radius:6px;font-size:11px;font-family:var(--mo);cursor:pointer;transition:.15s;align-self:flex-end}
.fclr:hover{border-color:var(--rd);color:var(--rd)}
tr.fin-hidden{display:none}
/* ── FACT/COBRO en publicados/pendientes ── */
.fc-cell{display:flex;align-items:center;gap:5px;flex-wrap:nowrap}
.fc-sep{color:var(--di);font-size:11px;font-family:var(--mo)}
/* ── FILTRO PCT CONDICIONAL ── */
.pct-filter-row{display:flex;gap:5px;align-items:center}
.fsel-op{min-width:130px}
.fsel-num{width:60px;background:var(--sf);border:1px solid var(--br2);color:var(--tx);padding:5px 8px;border-radius:6px;font-size:12px;font-family:var(--mo);outline:none;transition:.15s;-moz-appearance:textfield}
.fsel-num::-webkit-outer-spin-button,.fsel-num::-webkit-inner-spin-button{-webkit-appearance:none}
.fsel-num:focus,.fsel-num:hover{border-color:var(--ac)}
.exp-bar{display:flex;justify-content:flex-end;padding:12px 16px 0}
.exp-btn{background:linear-gradient(135deg,rgba(77,255,195,.12),rgba(77,255,195,.06));border:1px solid rgba(77,255,195,.35);color:var(--ac);padding:8px 16px;border-radius:8px;font-family:var(--sa);font-size:12.5px;font-weight:600;cursor:pointer;transition:.18s;display:flex;align-items:center;gap:7px;letter-spacing:.2px}
.exp-btn:hover{background:linear-gradient(135deg,rgba(77,255,195,.22),rgba(77,255,195,.12));border-color:var(--ac);box-shadow:0 0 12px rgba(77,255,195,.15)}
.exp-btn svg{opacity:.8}
/* ── EXPORT MODAL ── */
.exp-overlay{display:none;position:fixed;inset:0;background:rgba(0,0,0,.7);z-index:500;align-items:center;justify-content:center;backdrop-filter:blur(3px)}
.exp-overlay.open{display:flex}
.exp-modal{background:var(--sf2);border:1px solid var(--br2);border-radius:14px;padding:28px;width:560px;max-width:94vw;box-shadow:0 24px 64px rgba(0,0,0,.6);animation:mfade .18s ease}
@keyframes mfade{from{opacity:0;transform:translateY(-10px)}to{opacity:1;transform:translateY(0)}}
.exp-modal-hdr{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:6px}
.exp-modal-ttl{font-size:15px;font-weight:600;color:var(--tx)}
.exp-modal-ttl span{color:var(--ac)}
.exp-modal-close{background:transparent;border:none;color:var(--mu);font-size:18px;cursor:pointer;padding:2px 6px;border-radius:5px;line-height:1;transition:.12s}
.exp-modal-close:hover{color:var(--rd);background:var(--rdb)}
.exp-modal-sub{font-size:11px;font-family:var(--mo);color:var(--mu);letter-spacing:.4px;margin-bottom:16px}
.exp-modal-ctrl{display:flex;gap:6px;margin-bottom:12px}
.exp-ctrl-btn{background:transparent;border:1px solid var(--br2);color:var(--mu);padding:4px 11px;border-radius:6px;font-size:11px;font-family:var(--mo);cursor:pointer;transition:.14s}
.exp-ctrl-btn:hover{border-color:var(--ac);color:var(--ac)}
.exp-cols-grid{display:grid;grid-template-columns:1fr 1fr;gap:6px;max-height:260px;overflow-y:auto;margin-bottom:20px;padding-right:2px}
.exp-cols-grid::-webkit-scrollbar{width:4px}.exp-cols-grid::-webkit-scrollbar-thumb{background:var(--br2);border-radius:2px}
.exp-col-lbl{display:flex;align-items:center;gap:9px;padding:8px 11px;background:var(--sf);border:1px solid var(--br);border-radius:7px;cursor:pointer;font-size:12px;color:var(--mu);transition:.14s;user-select:none}
.exp-col-lbl:hover{border-color:rgba(77,255,195,.4);color:var(--tx)}
.exp-col-lbl input[type=checkbox]{accent-color:var(--ac);width:14px;height:14px;cursor:pointer;flex-shrink:0}
.exp-col-lbl.on{border-color:rgba(77,255,195,.3);color:var(--tx);background:rgba(77,255,195,.04)}
.exp-modal-footer{display:flex;align-items:center;justify-content:space-between;padding-top:16px;border-top:1px solid var(--br)}
.exp-footer-info{font-size:11px;font-family:var(--mo);color:var(--di)}
.exp-footer-btns{display:flex;gap:8px}
.exp-f-cancel{background:transparent;border:1px solid var(--br2);color:var(--mu);padding:8px 16px;border-radius:8px;font-family:var(--sa);font-size:12.5px;cursor:pointer;transition:.14s}
.exp-f-cancel:hover{border-color:var(--rd);color:var(--rd)}
.exp-f-pdf{background:var(--sf);border:1px solid var(--br2);color:var(--tx);padding:8px 16px;border-radius:8px;font-family:var(--sa);font-size:12.5px;font-weight:500;cursor:pointer;transition:.14s;display:flex;align-items:center;gap:6px}
.exp-f-pdf:hover{border-color:var(--ac);color:var(--ac)}
.exp-f-xlsx{background:linear-gradient(135deg,rgba(77,255,195,.15),rgba(77,255,195,.07));border:1px solid rgba(77,255,195,.4);color:var(--ac);padding:8px 18px;border-radius:8px;font-family:var(--sa);font-size:12.5px;font-weight:600;cursor:pointer;transition:.14s;display:flex;align-items:center;gap:6px}
.exp-f-xlsx:hover{background:linear-gradient(135deg,rgba(77,255,195,.25),rgba(77,255,195,.14));box-shadow:0 0 10px rgba(77,255,195,.2)}
"""

JS = r"""
var _dropOpen = false;

function fp(q) {
  var items = document.querySelectorAll('.dd-item');
  items.forEach(function(it) {
    var match = it.dataset.t.toLowerCase().indexOf(q.toLowerCase()) >= 0;
    it.style.display = match ? '' : 'none';
  });
  if (q.length > 0 && !_dropOpen) openDrop();
}

function openDrop() {
  _dropOpen = true;
  document.getElementById('dd-list').style.display = 'block';
  document.getElementById('dd-arrow').style.transform = 'rotate(180deg)';
}

function closeDrop() {
  _dropOpen = false;
  document.getElementById('dd-list').style.display = 'none';
  document.getElementById('dd-arrow').style.transform = 'rotate(0deg)';
}

function toggleDrop() {
  if (_dropOpen) { closeDrop(); } else { openDrop(); }
}

document.addEventListener('click', function(e) {
  var wrap = document.getElementById('dd-wrap');
  if (wrap && !wrap.contains(e.target)) closeDrop();
});

function selTalent(name) {
  document.getElementById('dd-input').value = name;
  document.getElementById('dd-selected').textContent = name;
  closeDrop();
  var sec = document.querySelector('#data .td[data-t="' + name.replace(/"/g,'&quot;') + '"]');
  if (!sec) return;
  document.getElementById('pp-content').innerHTML = sec.querySelector('.tp').innerHTML;
  document.getElementById('pe-content').innerHTML = sec.querySelector('.te').innerHTML;
  document.getElementById('pf-content').innerHTML = sec.querySelector('.tf').innerHTML;
  document.getElementById('cp').textContent = sec.dataset.pub;
  document.getElementById('ce').textContent = sec.dataset.pend;
  document.getElementById('cf').textContent = sec.dataset.fin;
  document.querySelectorAll('.tb').forEach(function(b){b.classList.remove('active');});
  document.querySelector('.tb[data-tab="p"]').classList.add('active');
  document.querySelectorAll('.panel').forEach(function(p){p.classList.remove('active');});
  document.getElementById('pp').classList.add('active');
  setTimeout(function() {
    var tw = document.querySelector('#pf .tw');
    if (tw) populateFinFilters(tw);
  }, 10);
}

function st(tab, btn) {
  document.querySelectorAll('.tb').forEach(function(b){b.classList.remove('active');});
  btn.classList.add('active');
  document.querySelectorAll('.panel').forEach(function(p){p.classList.remove('active');});
  document.getElementById('p'+tab).classList.add('active');
}

function tog(id) {
  var el = document.getElementById(id);
  if (el) el.classList.toggle('cl');
}

// ── FILTROS FINANZAS ──────────────────────────────────────────────────
function populateFinFilters(tw) {
  tw.querySelectorAll('.fsel:not(.fsel-op):not(.ftext)').forEach(function(sel) {
    var col = parseInt(sel.dataset.col);
    var vals = new Set();
    tw.querySelectorAll('tbody tr').forEach(function(tr) {
      var td = tr.cells[col];
      if (td) vals.add(td.dataset.v || '');
    });
    var current = sel.value;
    while (sel.options.length > 1) sel.remove(1);
    Array.from(vals).sort().forEach(function(v) {
      if (v) {
        var opt = document.createElement('option');
        opt.value = v; opt.textContent = v;
        sel.appendChild(opt);
      }
    });
    if (current) sel.value = current;
  });
}

// Muestra/oculta el input numérico según el operador elegido
function onPctOpChange(sel) {
  var numInput = sel.closest('.pct-filter-row').querySelector('.fsel-num');
  var needsNum = sel.value && sel.value !== 'pendiente';
  numInput.style.display = needsNum ? 'block' : 'none';
  if (!needsNum) numInput.value = '';
  applyFinFilter(sel.closest('.tw'));
}

function applyFinFilter(tw) {
  // Filtros de texto libre (contains, case-insensitive)
  var textFilters = [];
  tw.querySelectorAll('.ftext').forEach(function(inp) {
    if (inp.value.trim()) textFilters.push({col: parseInt(inp.dataset.col), val: inp.value.trim().toLowerCase()});
  });

  // Filtros de select normales (exacto)
  var normalFilters = [];
  tw.querySelectorAll('.fsel:not(.fsel-op):not(.ftext)').forEach(function(sel) {
    if (sel.value) normalFilters.push({col: parseInt(sel.dataset.col), val: sel.value});
  });

  // Filtro de porcentaje condicional
  var pctFilter = null;
  var opSel = tw.querySelector('.fsel-op');
  if (opSel && opSel.value) {
    var numInput = tw.querySelector('.fsel-num');
    var numVal = numInput ? parseFloat(numInput.value) : NaN;
    if (opSel.value === 'pendiente') {
      pctFilter = {type: 'pendiente'};
    } else if (!isNaN(numVal)) {
      pctFilter = {type: 'compare', op: opSel.value, val: numVal};
    }
  }

  tw.querySelectorAll('tbody tr').forEach(function(tr) {
    // Texto libre
    var show = textFilters.every(function(f) {
      var td = tr.cells[f.col];
      return td && (td.dataset.v || td.innerText || '').toLowerCase().indexOf(f.val) >= 0;
    });

    // Exacto
    if (show) show = normalFilters.every(function(f) {
      var td = tr.cells[f.col];
      return td && (td.dataset.v || '') === f.val;
    });

    // Porcentaje condicional
    if (show && pctFilter) {
      var td = tr.cells[6];
      var rawVal = td ? (td.dataset.v || '') : '';
      if (pctFilter.type === 'pendiente') {
        show = rawVal === 'pendiente_factura';
      } else {
        var cellNum = (rawVal === '100' || rawVal === 'pendiente_factura')
          ? (rawVal === '100' ? 100 : NaN)
          : parseFloat(rawVal);
        if (isNaN(cellNum)) {
          show = false;
        } else {
          var op = pctFilter.op;
          var v  = pctFilter.val;
          if      (op === 'lt')  show = cellNum <  v;
          else if (op === 'lte') show = cellNum <= v;
          else if (op === 'eq')  show = cellNum === v;
          else if (op === 'gte') show = cellNum >= v;
          else if (op === 'gt')  show = cellNum >  v;
        }
      }
    }

    tr.classList.toggle('fin-hidden', !show);
  });
}

function clearFinFilters(tw) {
  tw.querySelectorAll('.fsel').forEach(function(sel) { sel.value = ''; });
  tw.querySelectorAll('.ftext').forEach(function(inp) { inp.value = ''; });
  tw.querySelectorAll('.fsel-num').forEach(function(inp) {
    inp.value = '';
    inp.style.display = 'none';
  });
  tw.querySelectorAll('tbody tr').forEach(function(tr) { tr.classList.remove('fin-hidden'); });
}

// ── EXPORTAR (Excel / PDF) con modal de selección de columnas ───────
function getSelectedTalentName() {
  var el = document.getElementById('dd-selected');
  var name = el ? el.textContent.trim() : '';
  return (!name || name === 'Seleccioná un talento...') ? '' : name;
}

function collectPanelData(panelId) {
  var content = document.getElementById(panelId + '-content');
  if (!content) return {header: [], rows: []};
  var groups = content.querySelectorAll('.mg');
  var header = [];
  var rows = [];
  if (groups.length) {
    groups.forEach(function(g) {
      var mtEl = g.querySelector('.mt');
      var mes = mtEl ? (mtEl.childNodes[0].textContent || '').trim() : '';
      var table = g.querySelector('table');
      if (!table) return;
      if (!header.length) {
        header = ['Mes'];
        table.querySelectorAll('thead th').forEach(function(th) { header.push(th.textContent.trim()); });
      }
      table.querySelectorAll('tbody tr').forEach(function(tr) {
        if (tr.classList.contains('fin-hidden')) return;
        var row = [mes];
        tr.querySelectorAll('td').forEach(function(td) { row.push(td.innerText.trim()); });
        rows.push(row);
      });
    });
  } else {
    var table = content.querySelector('table');
    if (table) {
      table.querySelectorAll('thead th').forEach(function(th) { header.push(th.textContent.trim()); });
      table.querySelectorAll('tbody tr').forEach(function(tr) {
        if (tr.classList.contains('fin-hidden')) return;
        var row = [];
        tr.querySelectorAll('td').forEach(function(td) { row.push(td.innerText.trim()); });
        rows.push(row);
      });
    }
  }
  return {header: header, rows: rows};
}

var _expCtx = {};

function openExportModal(panelId, sheetName) {
  var talent = getSelectedTalentName();
  if (!talent) { alert('Seleccioná un talento primero.'); return; }
  var data = collectPanelData(panelId);
  if (!data.rows.length) { alert('No hay datos para exportar.'); return; }

  _expCtx = {panelId: panelId, sheetName: sheetName, talent: talent, data: data};

  // Render column checkboxes
  var grid = document.getElementById('exp-cols-grid');
  grid.innerHTML = '';
  data.header.forEach(function(h, i) {
    var lbl = document.createElement('label');
    lbl.className = 'exp-col-lbl on';
    lbl.innerHTML = '<input type="checkbox" value="' + i + '" checked> ' + (h || '—');
    lbl.querySelector('input').addEventListener('change', function() {
      lbl.classList.toggle('on', this.checked);
      updateExpCount();
    });
    grid.appendChild(lbl);
  });

  document.getElementById('exp-modal-ttl-tab').textContent = sheetName;
  updateExpCount();
  document.getElementById('exp-overlay').classList.add('open');
}

function closeExportModal() {
  document.getElementById('exp-overlay').classList.remove('open');
}

function expSelAll(val) {
  document.querySelectorAll('#exp-cols-grid input[type=checkbox]').forEach(function(cb) {
    cb.checked = val;
    cb.closest('.exp-col-lbl').classList.toggle('on', val);
  });
  updateExpCount();
}

function updateExpCount() {
  var n = document.querySelectorAll('#exp-cols-grid input[type=checkbox]:checked').length;
  var total = document.querySelectorAll('#exp-cols-grid input[type=checkbox]').length;
  document.getElementById('exp-col-count').textContent = n + ' de ' + total + ' columnas seleccionadas';
}

function getFilteredData() {
  var data = _expCtx.data;
  var idxs = Array.from(
    document.querySelectorAll('#exp-cols-grid input[type=checkbox]:checked')
  ).map(function(cb) { return parseInt(cb.value); });
  if (!idxs.length) { alert('Seleccioná al menos una columna.'); return null; }
  return {
    header: idxs.map(function(i) { return data.header[i]; }),
    rows: data.rows.map(function(row) { return idxs.map(function(i) { return row[i] || ''; }); })
  };
}

function doExportXLSX() {
  var d = getFilteredData();
  if (!d) return;
  if (typeof XLSX === 'undefined') { alert('No se pudo cargar el módulo de Excel.'); return; }
  var ws = XLSX.utils.aoa_to_sheet([d.header].concat(d.rows));
  // Auto column widths
  var wscols = d.header.map(function(h, i) {
    var maxLen = Math.max(h.length, ...d.rows.map(function(r){ return (r[i]||'').length; }));
    return {wch: Math.min(Math.max(maxLen + 2, 10), 40)};
  });
  ws['!cols'] = wscols;
  var wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, _expCtx.sheetName.substring(0, 31));
  XLSX.writeFile(wb, _expCtx.talent + ' - ' + _expCtx.sheetName + '.xlsx');
  closeExportModal();
}

function doExportPDF() {
  var d = getFilteredData();
  if (!d) return;
  if (typeof window.jspdf === 'undefined') { alert('No se pudo cargar el módulo de PDF.'); return; }
  var doc = new window.jspdf.jsPDF({orientation: 'landscape', unit: 'pt', format: 'a4'});
  doc.setFontSize(14);
  doc.setTextColor(77, 255, 195);
  doc.text(_expCtx.talent, 30, 30);
  doc.setTextColor(228, 232, 244);
  doc.setFontSize(11);
  doc.text(_expCtx.sheetName, 30, 46);
  doc.setFontSize(8);
  doc.setTextColor(122, 129, 154);
  doc.text('Generado: ' + new Date().toLocaleString('es-AR'), 30, 58);
  doc.autoTable({
    head: [d.header],
    body: d.rows,
    startY: 68,
    styles: {fontSize: 7, cellPadding: 3.5, textColor: [228, 232, 244], lineColor: [37, 42, 58]},
    headStyles: {fillColor: [19, 22, 31], textColor: [122, 129, 154], fontStyle: 'bold', fontSize: 7},
    alternateRowStyles: {fillColor: [28, 32, 48]},
    bodyStyles: {fillColor: [11, 13, 19]},
    margin: {left: 28, right: 28},
    tableLineColor: [37, 42, 58], tableLineWidth: 0.3
  });
  doc.save(_expCtx.talent + ' - ' + _expCtx.sheetName + '.pdf');
  closeExportModal();
}
"""


def generar_html(talentos):
    now = datetime.now().strftime("%d/%m/%Y %H:%M")

    dd_items = "\n".join(
        f'<div class="dd-item" data-t="{n.replace(chr(34), "&quot;")}" onclick="selTalent(this.dataset.t)">{n}</div>'
        for n in sorted(talentos.keys())
    )

    sections = ""
    for name, data in talentos.items():
        ne = name.replace('"', '&quot;').replace("'", "&#39;")
        sections += f"""
<div class="td" data-t="{ne}"
     data-pub="{len(data["published"])}"
     data-pend="{len(data["pending"])}"
     data-fin="{len(data["finance"])}">
  <div class="tp">{render_published(data["published"], data["finance_by_so"])}</div>
  <div class="te">{render_pending(data["pending"], data["finance_by_so"])}</div>
  <div class="tf">{render_finance(data["finance"])}</div>
</div>"""

    # Wire up the pct operator select — needs to call onPctOpChange
    # We inject the onchange directly in the HTML template above (render_finance),
    # but since it's generated once per talent and reused, the fsel-op already has
    # onchange="applyFinFilter(...)" — we override it here via a global delegated listener
    # added in the JS block below.

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Talentos ZAS — Finanzas</title>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@300;400;500;600&display=swap" rel="stylesheet">
<script src="https://cdnjs.cloudflare.com/ajax/libs/xlsx/0.18.5/xlsx.full.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/jspdf-autotable/3.8.2/jspdf.plugin.autotable.min.js"></script>
<style>{CSS}</style>
</head>
<body>
<div class="hdr">
  <div class="lo">
    <div class="lm">ZAS</div>
    <div><div class="lt">Seguimiento de Talentos</div><div class="ls">FINANZAS · ODOO</div></div>
  </div>
  <span class="lu">Generado: {now}</span>
</div>
<div class="ts">
  <div class="tl">Talento</div>
  <div class="dd-wrap" id="dd-wrap">
    <div class="dd-trigger" onclick="toggleDrop()">
      <span class="dd-selected placeholder" id="dd-selected">Seleccioná un talento...</span>
      <span class="dd-arrow" id="dd-arrow">▾</span>
    </div>
    <div class="dd-list" id="dd-list">
      <div class="dd-search">
        <input type="text" id="dd-input" placeholder="Buscar talento..." oninput="fp(this.value)" autocomplete="off">
      </div>
      <div class="dd-items" id="dd-items">
{dd_items}
      </div>
    </div>
  </div>
</div>
<div class="tbar">
  <button class="tb active" data-tab="p" onclick="st('p',this)">Publicados <span class="tc" id="cp">—</span></button>
  <button class="tb" data-tab="e" onclick="st('e',this)">Pendientes <span class="tc" id="ce">—</span></button>
  <button class="tb" data-tab="f" onclick="st('f',this)">Finanzas <span class="tc" id="cf">—</span></button>
</div>
<div class="main">
  <div class="panel active" id="pp">
    <div class="exp-bar">
      <button class="exp-btn" onclick="openExportModal('pp','Publicados')">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
        Exportar
      </button>
    </div>
    <div id="pp-content"><div class="ns"><div class="ar">↑</div><div>Seleccioná un talento</div></div></div>
  </div>
  <div class="panel" id="pe">
    <div class="exp-bar">
      <button class="exp-btn" onclick="openExportModal('pe','Pendientes')">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
        Exportar
      </button>
    </div>
    <div id="pe-content"><div class="ns"><div class="ar">↑</div><div>Seleccioná un talento</div></div></div>
  </div>
  <div class="panel" id="pf">
    <div class="exp-bar">
      <button class="exp-btn" onclick="openExportModal('pf','Finanzas')">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
        Exportar
      </button>
    </div>
    <div id="pf-content"><div class="ns"><div class="ar">↑</div><div>Seleccioná un talento</div></div></div>
  </div>
</div>
<div class="exp-overlay" id="exp-overlay" onclick="if(event.target===this)closeExportModal()">
  <div class="exp-modal">
    <div class="exp-modal-hdr">
      <div class="exp-modal-ttl">Exportar — <span id="exp-modal-ttl-tab"></span></div>
      <button class="exp-modal-close" onclick="closeExportModal()">✕</button>
    </div>
    <div class="exp-modal-sub">Seleccioná las columnas a incluir en el archivo</div>
    <div class="exp-modal-ctrl">
      <button class="exp-ctrl-btn" onclick="expSelAll(true)">✓ Todas</button>
      <button class="exp-ctrl-btn" onclick="expSelAll(false)">✕ Ninguna</button>
    </div>
    <div class="exp-cols-grid" id="exp-cols-grid"></div>
    <div class="exp-modal-footer">
      <span class="exp-footer-info" id="exp-col-count"></span>
      <div class="exp-footer-btns">
        <button class="exp-f-cancel" onclick="closeExportModal()">Cancelar</button>
        <button class="exp-f-pdf" onclick="doExportPDF()">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
          PDF
        </button>
        <button class="exp-f-xlsx" onclick="doExportXLSX()">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M8 12l2.5 3L14 9"/></svg>
          Excel
        </button>
      </div>
    </div>
  </div>
</div>
<div style="display:none" id="data">{sections}</div>
<script>{JS}
// Delegated listener para el selector de operador de porcentaje
document.addEventListener('change', function(e) {{
  if (e.target.classList.contains('fsel-op')) {{
    onPctOpChange(e.target);
  }}
}});
</script>
</body>
</html>"""


if __name__ == "__main__":
    print("=" * 55)
    print("  Dashboard Talentos ZAS")
    print("=" * 55)
    try:
        talent_names, subtareas, task_talent_map, task_amount_map, so_map, \
            client_inv_map, po_map, vendor_inv_map = bajar_datos()

        print("\nConstruyendo datos...")
        talentos = construir_datos(talent_names, subtareas, task_talent_map, task_amount_map,
                                   so_map, client_inv_map, po_map, vendor_inv_map)
        print(f"  ✓ {len(talentos)} talentos con datos")

        print("\nGenerando HTML...")
        html = generar_html(talentos)
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write(html)

        total_pub  = sum(len(d["published"]) for d in talentos.values())
        total_pend = sum(len(d["pending"])   for d in talentos.values())
        total_fin  = sum(len(d["finance"])   for d in talentos.values())
        print(f"\n✓ Generado: {OUTPUT_FILE}")
        print(f"  Talentos:   {len(talentos)}")
        print(f"  Publicados: {total_pub}  |  Pendientes: {total_pend}  |  Ventas: {total_fin}")
        print("=" * 55)

    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
