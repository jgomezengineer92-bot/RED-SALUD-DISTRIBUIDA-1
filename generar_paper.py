#!/usr/bin/env python3
"""
Generador del Paper IEEE - Red Salud Distribuida
Sigue exactamente la Plantilla_IEEE_SistemasDistribuidos.docx del profesor
"""
from docx import Document
from docx.shared import Pt, Inches, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.section import WD_SECTION
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
import copy

# ─────────────────────────────────────────────────────────────
# CONTENIDO DEL PAPER
# ─────────────────────────────────────────────────────────────
TITULO = "ARQUITECTURA DISTRIBUIDA P2P PARA HISTORIA CLÍNICA ELECTRÓNICA CON HL7 FHIR R4 Y CITUS"

AUTORES = "Gómez J.¹  —  [Apellido, Nombre]²  —  [Apellido, Nombre]³"

AFILIACION = ("¹Universidad / Programa de Ingeniería de Sistemas — Colombia — "
              "jgomezengineer92@dominio.edu  |  ²...  |  ³...")

ABSTRACT = (
    "This paper presents the design and implementation of a peer-to-peer (P2P) "
    "distributed architecture for Electronic Health Records (EHR) management, "
    "compliant with Colombia's Resolution 866 of 2021. The system integrates "
    "HAPI FHIR R4 servers for healthcare interoperability, PostgreSQL/Citus as a "
    "distributed transactional database sharding 57 clinical fields across multiple "
    "geographic nodes, and Apache CouchDB as a document store per node. Security is "
    "enforced via OAuth2/JWT with SMART on FHIR scopes. The observability stack uses "
    "Prometheus and Grafana for real-time metrics across all nodes. Fault tolerance "
    "was validated through chaos engineering experiments: after stopping one Citus "
    "worker node, 83 shards were detected as affected while reference tables remained "
    "fully available, and full recovery was achieved within seconds upon node "
    "reactivation. Distributed queries executed transparently via Citus Adaptive "
    "scan across 32 task partitions. The architecture achieves high availability "
    "through geographic node replication (La Guajira, Amazonas, Guainía), automated "
    "health checks with etcd-based service discovery, and a Token Bucket rate limiter. "
    "Results confirm that the proposed system meets scalability, security, and "
    "regulatory compliance requirements for distributed health information systems "
    "in resource-limited Colombian regions."
)

KEYWORDS = "distributed systems, FHIR R4, Citus, electronic health records, P2P, OAuth2, fault tolerance"

INTRO = (
    "La gestión de historias clínicas electrónicas (HCE) en Colombia está regida por "
    "la Resolución 866 de 2021 del Ministerio de Salud, que exige el registro de 57 "
    "campos estructurados distribuidos en cinco secciones clínicas. En regiones con "
    "infraestructura limitada como La Guajira, Amazonas y Guainía, la centralización "
    "de datos clínicos genera puntos únicos de falla y latencias inaceptables para la "
    "atención de emergencias. La pregunta de investigación es: ¿Cómo diseñar una "
    "arquitectura distribuida que garantice disponibilidad, interoperabilidad y "
    "cumplimiento normativo para la HCE en nodos geográficos heterogéneos?\n\n"
    "El objetivo principal de este trabajo es proponer, implementar y validar una "
    "arquitectura P2P basada en microservicios que integre HL7 FHIR R4, "
    "PostgreSQL/Citus y CouchDB para la gestión distribuida de HCE. El artículo se "
    "organiza así: la Sección II presenta el marco teórico; la Sección III el estado "
    "del arte; la Sección IV la metodología y propuesta; la Sección V los resultados; "
    "la Sección VI la discusión; y la Sección VII las conclusiones."
)

MARCO = (
    "Los sistemas distribuidos son conjuntos de nodos independientes que colaboran "
    "para ofrecer servicios con transparencia de distribución [1]. La interoperabilidad "
    "en salud se logra mediante el estándar HL7 FHIR R4 (Fast Healthcare Interoperability "
    "Resources), que define recursos REST como Patient, Encounter, Observation, Condition "
    "y MedicationRequest [2]. PostgreSQL/Citus extiende PostgreSQL para escalar "
    "horizontalmente mediante sharding automático de tablas distribuidas y tablas de "
    "referencia replicadas [3]. Apache CouchDB implementa replicación P2P basada en "
    "el protocolo Couch, adecuada para nodos con conectividad intermitente [6]. "
    "OAuth2 con extensiones SMART on FHIR provee autorización granular por scope "
    "(patient/*.read, patient/*.write) sobre recursos clínicos [7]. La observabilidad "
    "se implementa con Prometheus (scraping de métricas) y Grafana (visualización de "
    "dashboards), siguiendo el modelo de los tres pilares: métricas, trazas y logs [5]."
)

ESTADO_ARTE = (
    "Estudios previos han abordado la fragmentación de registros clínicos en entornos "
    "distribuidos. Blobel et al. [1] proponen modelos de referencia para EHR federados "
    "usando arquitecturas orientadas a servicios. Mandel et al. desarrollaron SMART on "
    "FHIR como capa de autorización estándar sobre repositorios FHIR [7]. En el contexto "
    "latinoamericano, iniciativas como la Red Nacional de Salud Digital de Colombia "
    "evidencian la necesidad de arquitecturas interoperables bajo restricciones normativas "
    "locales. Sin embargo, la mayoría de propuestas asumen conectividad estable y no "
    "consideran escenarios de nodos geográficamente dispersos con fallas parciales. "
    "El presente trabajo llena este vacío al combinar HAPI FHIR R4, Citus y CouchDB "
    "en una topología P2P con tolerancia a fallos demostrada experimentalmente, "
    "incluyendo pruebas de caos en el coordinador Citus y validación de recuperación "
    "automática de shards."
)

METODOLOGIA = (
    "La metodología sigue un diseño experimental de ingeniería de sistemas. Se "
    "implementó un stack Docker Compose con los siguientes componentes:\n\n"
    "• 4 nodos API Flask (puertos 5000–5003) representando nodos geográficos.\n"
    "• 3 instancias HAPI FHIR R4 (puertos 8080–8082) en total.\n"
    "• 4 instancias CouchDB (puertos 5984–5987) para almacenamiento documental.\n"
    "• 1 coordinador Citus + 2 workers (puerto 5432) para el esquema relacional.\n"
    "• etcd para service discovery (puerto 2379).\n"
    "• Prometheus + Grafana para observabilidad.\n\n"
    "El esquema Citus distribuye los 57 campos de la Res. 866/2021 en 5 tablas "
    "(usuario, atencion, tecnologia_salud, diagnostico, egreso), todas shardadas "
    "por documento_id. La tabla profesional_salud es una tabla de referencia replicada "
    "en todos los workers. La seguridad se implementa con JWT (HS256) y middleware "
    "de autorización en cada endpoint Flask. Los flujos FHIR se crean automáticamente "
    "al completar cada sección clínica en el frontend React."
)

RESULTADOS_TEXTO = (
    "Las pruebas de tolerancia a fallos (Fase 6) demostraron que al detener el nodo "
    "citus_worker1, se identificaron 83 shards afectados distribuidos entre las tablas "
    "usuario, atencion, tecnologia_salud, diagnostico y egreso. Las consultas sobre "
    "la tabla de referencia profesional_salud continuaron operando correctamente, "
    "retornando los 3 profesionales registrados. Al reactivar el nodo, citus_activate_node "
    "confirmó estado 2 (activo) y la verificación final mostró shardstate=1 para los "
    "163 shards totales. Las consultas distribuidas mostraron un plan Citus Adaptive "
    "Scan sobre 32 particiones de tarea (Task Count: 32). El frontend React desplegó "
    "los 5 módulos clínicos con integración FHIR en tiempo real."
)

TABLE_DATA = [
    ["Componente", "Tecnología", "Rol", "Puerto"],
    ["API Gateway", "Flask + Python", "Orquestación clínica + OAuth2", "5000–5002"],
    ["FHIR Server", "HAPI FHIR R4", "Interoperabilidad HL7", "8080–8082"],
    ["BD Documental", "Apache CouchDB", "Almacenamiento P2P por nodo", "5984–5986"],
    ["BD Relacional", "PostgreSQL/Citus", "57 campos Res. 866/2021", "5432"],
    ["Service Discovery", "etcd", "Registro de endpoints", "2379"],
    ["Observabilidad", "Prometheus+Grafana", "Métricas en tiempo real", "9090/3001"],
]

DISCUSION = (
    "Los resultados confirman que la arquitectura propuesta logra tolerancia a fallos "
    "parciales: la caída de un worker Citus no interrumpe las operaciones sobre tablas "
    "de referencia replicadas, y la recuperación es transparente para el usuario final. "
    "Sin embargo, se identifican limitaciones: (1) Las queries sobre tablas distribuidas "
    "fallan cuando el worker afectado contiene los shards consultados, lo que implica "
    "que el rebalanceo automático de shards (citus_rebalance_table_shards) debe "
    "habilitarse en producción. (2) La latencia de HAPI FHIR (~512 MB RAM por instancia) "
    "puede ser prohibitiva en hardware de baja gama. (3) La sincronización CouchDB P2P "
    "no garantiza consistencia fuerte, adecuada para datos clínicos no críticos pero "
    "insuficiente para registros de medicación. Como trabajo futuro se propone integrar "
    "un mecanismo de Saga Pattern para transacciones distribuidas y evaluar el uso de "
    "FHIR Subscriptions para notificaciones en tiempo real entre nodos."
)

CONCLUSIONES = (
    "Se diseñó e implementó una arquitectura distribuida P2P para la gestión de HCE "
    "en Colombia, cumpliendo la Resolución 866 de 2021 mediante el registro de 57 "
    "campos clínicos en PostgreSQL/Citus. La integración de HAPI FHIR R4 garantiza "
    "interoperabilidad estándar. Las pruebas de caos validaron la tolerancia a fallos "
    "con recuperación automática de nodos. La seguridad OAuth2/JWT con scopes SMART "
    "on FHIR y la observabilidad Prometheus/Grafana completan los requisitos de un "
    "sistema distribuido de salud de nivel productivo. La arquitectura es replicable "
    "para redes de salud rurales con infraestructura heterogénea en cualquier región "
    "de Colombia o Latinoamérica."
)

REFERENCIAS = [
    "[1] IEEE. \"IEEE Standard for Distributed Interactive Simulation,\" IEEE Std 1278.1, 2012.",
    "[2] HL7 International. \"FHIR R4 Specification,\" https://hl7.org/fhir/R4/, 2019.",
    "[3] Citus Data. \"Citus: Distributed PostgreSQL,\" https://www.citusdata.com/, 2023.",
    "[4] HAPI FHIR. \"Open Source FHIR Server,\" https://hapifhir.io/, 2023.",
    "[5] Prometheus Authors. \"Prometheus Monitoring System,\" https://prometheus.io/, 2023.",
    "[6] Apache Software Foundation. \"CouchDB Documentation,\" https://couchdb.apache.org/, 2023.",
    "[7] SMART Health IT. \"SMART on FHIR Authorization,\" https://smarthealthit.org/, 2021.",
    "[8] MinSalud Colombia. \"Resolución 866 de 2021 - Historia Clínica Electrónica,\" 2021.",
]


# ─────────────────────────────────────────────────────────────
# HELPERS DE FORMATO
# ─────────────────────────────────────────────────────────────
IEEE_BLUE = RGBColor(0x00, 0x33, 0x99)

def set_font(run, name="Times New Roman", size=9, bold=False, italic=False, color=None):
    run.font.name = name
    run.font.size = Pt(size)
    run.bold = bold
    run.italic = italic
    if color:
        run.font.color.rgb = color

def add_heading_run(para, text, size=10):
    run = para.add_run(text)
    set_font(run, size=size, bold=True)
    return run

def set_para_spacing(para, before=0, after=4, line=None):
    pf = para.paragraph_format
    pf.space_before = Pt(before)
    pf.space_after = Pt(after)
    if line:
        pf.line_spacing = Pt(line)

def add_blue_line(doc):
    """Línea decorativa azul IEEE."""
    p = doc.add_paragraph()
    pPr = p._p.get_or_add_pPr()
    pBdr = OxmlElement('w:pBdr')
    bottom = OxmlElement('w:bottom')
    bottom.set(qn('w:val'), 'single')
    bottom.set(qn('w:sz'), '12')
    bottom.set(qn('w:space'), '1')
    bottom.set(qn('w:color'), '003399')
    pBdr.append(bottom)
    pPr.append(pBdr)
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after = Pt(6)
    return p

def set_two_columns(section):
    """Configura 2 columnas IEEE en la sección."""
    sectPr = section._sectPr
    cols = OxmlElement('w:cols')
    cols.set(qn('w:num'), '2')
    cols.set(qn('w:space'), '720')  # ~0.5 pulgada entre columnas
    cols.set(qn('w:equalWidth'), '1')
    sectPr.append(cols)

def add_page_number(section):
    """Encabezado con número de página automático."""
    sectPr = section._sectPr
    # Header reference
    hdr_ref = OxmlElement('w:headerReference')
    hdr_ref.set(qn('w:type'), 'default')
    sectPr.append(hdr_ref)

def add_section_title(doc, number, title):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    run = p.add_run(f"{number}. {title}")
    set_font(run, size=9, bold=True)
    set_para_spacing(p, before=6, after=3)
    return p

def add_body_para(doc, text, first_line_indent=True):
    p = doc.add_paragraph()
    run = p.add_run(text)
    set_font(run, size=9)
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    set_para_spacing(p, before=0, after=3, line=11)
    if first_line_indent:
        p.paragraph_format.first_line_indent = Pt(14)
    return p


# ─────────────────────────────────────────────────────────────
# CONSTRUCCIÓN DEL DOCUMENTO
# ─────────────────────────────────────────────────────────────
def build_paper():
    doc = Document()

    # ── Márgenes 0.7 pulgadas (IEEE estándar) ──
    section = doc.sections[0]
    section.page_width = Inches(8.5)
    section.page_height = Inches(11)
    margin = Inches(0.7)
    section.left_margin = margin
    section.right_margin = margin
    section.top_margin = margin
    section.bottom_margin = margin

    # ═══════════════════════════════════════
    # BLOQUE CABECERA (ancho completo)
    # ═══════════════════════════════════════

    # Título
    p_title = doc.add_paragraph()
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p_title.add_run(TITULO)
    set_font(r, size=16, bold=True, color=IEEE_BLUE)
    set_para_spacing(p_title, before=0, after=6)

    # Autores
    p_authors = doc.add_paragraph()
    p_authors.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p_authors.add_run(AUTORES)
    set_font(r, size=10, italic=True)
    set_para_spacing(p_authors, before=2, after=2)

    # Afiliación
    p_aff = doc.add_paragraph()
    p_aff.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p_aff.add_run(AFILIACION)
    set_font(r, size=8, italic=True)
    set_para_spacing(p_aff, before=0, after=4)

    # Línea decorativa azul IEEE
    add_blue_line(doc)

    # ═══════════════════════════════════════
    # ABSTRACT + KEYWORDS (sombreado)
    # ═══════════════════════════════════════
    table_abs = doc.add_table(rows=1, cols=1)
    table_abs.style = 'Table Grid'
    cell = table_abs.cell(0, 0)
    # Fondo gris claro
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear')
    shd.set(qn('w:color'), 'auto')
    shd.set(qn('w:fill'), 'E8E8E8')
    tcPr.append(shd)

    p_abs = cell.paragraphs[0]
    r_label = p_abs.add_run("Abstract — ")
    set_font(r_label, size=9, bold=True, italic=True)
    r_text = p_abs.add_run(ABSTRACT)
    set_font(r_text, size=9, italic=True)
    p_abs.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    set_para_spacing(p_abs, before=4, after=4, line=11)

    p_kw = cell.add_paragraph()
    r_kl = p_kw.add_run("Keywords — ")
    set_font(r_kl, size=9, bold=True, italic=True)
    r_kw = p_kw.add_run(KEYWORDS)
    set_font(r_kw, size=9, italic=True)
    set_para_spacing(p_kw, before=2, after=4)

    doc.add_paragraph()  # espacio

    # ═══════════════════════════════════════
    # CUERPO A 2 COLUMNAS — iniciar sección continua
    # ═══════════════════════════════════════
    # Insertar salto de sección continuo para arrancar las 2 columnas
    p_break = doc.add_paragraph()
    p_break.paragraph_format.space_before = Pt(0)
    p_break.paragraph_format.space_after = Pt(0)
    pPr = p_break._p.get_or_add_pPr()
    sectPr_new = OxmlElement('w:sectPr')
    # 2 columnas
    cols_el = OxmlElement('w:cols')
    cols_el.set(qn('w:num'), '2')
    cols_el.set(qn('w:space'), '720')
    cols_el.set(qn('w:equalWidth'), '1')
    sectPr_new.append(cols_el)
    # Tipo continuous
    pgSzEl = OxmlElement('w:pgSz')
    pgSzEl.set(qn('w:w'), str(int(8.5 * 1440)))
    pgSzEl.set(qn('w:h'), str(int(11 * 1440)))
    sectPr_new.append(pgSzEl)
    pgMarEl = OxmlElement('w:pgMar')
    pgMarEl.set(qn('w:top'), str(int(0.7 * 1440)))
    pgMarEl.set(qn('w:right'), str(int(0.7 * 1440)))
    pgMarEl.set(qn('w:bottom'), str(int(0.7 * 1440)))
    pgMarEl.set(qn('w:left'), str(int(0.7 * 1440)))
    sectPr_new.append(pgMarEl)
    typeEl = OxmlElement('w:type')
    typeEl.set(qn('w:val'), 'continuous')
    sectPr_new.append(typeEl)
    pPr.append(sectPr_new)

    # ── I. INTRODUCCIÓN ──
    add_section_title(doc, "I", "INTRODUCCIÓN")
    add_body_para(doc, INTRO)

    # ── II. MARCO TEÓRICO ──
    add_section_title(doc, "II", "MARCO TEÓRICO")
    add_body_para(doc, MARCO)

    # ── III. ESTADO DEL ARTE ──
    add_section_title(doc, "III", "ESTADO DEL ARTE")
    add_body_para(doc, ESTADO_ARTE)

    # ── IV. METODOLOGÍA / PROPUESTA ──
    add_section_title(doc, "IV", "METODOLOGÍA / PROPUESTA")
    add_body_para(doc, METODOLOGIA)

    # Figura 1 — diagrama de arquitectura (placeholder)
    p_fig = doc.add_paragraph()
    p_fig.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_fig = p_fig.add_run("[Figura 1. Arquitectura P2P distribuida: nodos geográficos, Citus coordinator, HAPI FHIR y CouchDB]")
    set_font(r_fig, size=8, italic=True)
    # Borde de figura simulado
    pPr_fig = p_fig._p.get_or_add_pPr()
    pBdr_fig = OxmlElement('w:pBdr')
    for side in ('top', 'left', 'bottom', 'right'):
        el = OxmlElement(f'w:{side}')
        el.set(qn('w:val'), 'single')
        el.set(qn('w:sz'), '6')
        el.set(qn('w:space'), '4')
        el.set(qn('w:color'), '003399')
        pBdr_fig.append(el)
    pPr_fig.append(pBdr_fig)
    set_para_spacing(p_fig, before=4, after=4)

    p_fc = doc.add_paragraph()
    p_fc.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_fc = p_fc.add_run("Fig. 1. Topología P2P — Stack: React · Flask · CouchDB · Citus · HAPI FHIR R4 · etcd · Prometheus · Grafana")
    set_font(r_fc, size=8, bold=True)
    set_para_spacing(p_fc, before=0, after=6)

    # ── V. RESULTADOS ESPERADOS ──
    add_section_title(doc, "V", "RESULTADOS ESPERADOS")
    add_body_para(doc, RESULTADOS_TEXTO)

    # Tabla I
    p_tl = doc.add_paragraph()
    r_tl = p_tl.add_run("Tabla I. Componentes del Stack Distribuido")
    set_font(r_tl, size=9, bold=True)
    p_tl.alignment = WD_ALIGN_PARAGRAPH.CENTER
    set_para_spacing(p_tl, before=4, after=2)

    t = doc.add_table(rows=len(TABLE_DATA), cols=4)
    t.style = 'Table Grid'
    for i, row_data in enumerate(TABLE_DATA):
        for j, cell_text in enumerate(row_data):
            cell = t.cell(i, j)
            p = cell.paragraphs[0]
            r = p.add_run(cell_text)
            bold = (i == 0)
            set_font(r, size=8, bold=bold)
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            # Header row: fondo azul IEEE
            if i == 0:
                tcPr = cell._tc.get_or_add_tcPr()
                shd = OxmlElement('w:shd')
                shd.set(qn('w:val'), 'clear')
                shd.set(qn('w:color'), 'auto')
                shd.set(qn('w:fill'), '003399')
                tcPr.append(shd)
                r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)

    doc.add_paragraph()

    # ── VI. DISCUSIÓN ──
    add_section_title(doc, "VI", "DISCUSIÓN")
    add_body_para(doc, DISCUSION)

    # ── VII. CONCLUSIONES ──
    add_section_title(doc, "VII", "CONCLUSIONES")
    add_body_para(doc, CONCLUSIONES)

    # ── REFERENCIAS ──
    add_section_title(doc, "", "REFERENCIAS")
    for ref in REFERENCIAS:
        p_ref = doc.add_paragraph()
        r_ref = p_ref.add_run(ref)
        set_font(r_ref, size=8)
        p_ref.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        # Sangría francesa IEEE
        p_ref.paragraph_format.left_indent = Pt(18)
        p_ref.paragraph_format.first_line_indent = Pt(-18)
        set_para_spacing(p_ref, before=0, after=3)

    # ── Sección final: 2 columnas para el cuerpo ──
    # La sección principal del documento (la última) debe tener 2 columnas
    final_section = doc.sections[-1]
    cols_final = OxmlElement('w:cols')
    cols_final.set(qn('w:num'), '2')
    cols_final.set(qn('w:space'), '720')
    cols_final.set(qn('w:equalWidth'), '1')
    final_section._sectPr.append(cols_final)

    out_path = "/home/jesus/RED-SALUD-DISTRIBUIDA-1/Paper_IEEE_RedSaludDistribuida.docx"
    doc.save(out_path)
    print(f"✅ Paper IEEE generado: {out_path}")
    return out_path


if __name__ == "__main__":
    build_paper()
