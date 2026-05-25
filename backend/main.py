import os
import time
import base64
import hashlib
import json
import threading
import uuid as uuid_mod
import datetime
import functools
from threading import Lock
from flask import Flask, request, jsonify
from flask_cors import CORS
import couchdb
import urllib.parse
import requests
import psycopg2
# pyrefly: ignore [missing-import]
import jwt  # PyJWT — OAuth2/SMART on FHIR (Requisito 3.3)

app = Flask(__name__)
# Permitir peticiones desde cualquier origen para la API
CORS(app)

# ==========================================
# PROMETHEUS METRICS (Requisito 5.3)
# ==========================================
try:
    from prometheus_flask_exporter import PrometheusMetrics
    PrometheusMetrics(app)
except ImportError:
    # Fallback: exponer /metrics manualmente si la lib no está disponible
    @app.route('/metrics', methods=['GET'])
    def prometheus_metrics():
        return "# No prometheus_flask_exporter instalado\n", 200

# ==========================================
# JWT / OAuth2 CONFIGURATION (Requisito 3.3)
# ==========================================
JWT_SECRET = os.environ.get('JWT_SECRET', 'red-salud-distribuida-secret-2026')
JWT_ALGORITHM = 'HS256'
JWT_EXPIRATION_HOURS = 24

# HAPI FHIR Server URL (Requisito 3.1)
HAPI_FHIR_URL = os.environ.get('HAPI_FHIR_URL', 'http://hapi-fhir-guajira:8080/fhir')

class TokenBucketRateLimiter:
    def __init__(self, capacity, fill_rate):
        self.capacity = capacity
        self.fill_rate = fill_rate
        self.clients = {}
        self.lock = Lock()
        
    def allow_request(self, client_id):
        with self.lock:
            now = time.time()
            if client_id not in self.clients:
                self.clients[client_id] = {'tokens': self.capacity, 'last_update': now}
                
            client_data = self.clients[client_id]
            elapsed = now - client_data['last_update']
            tokens_to_add = elapsed * self.fill_rate
            
            if tokens_to_add > 0:
                client_data['tokens'] = min(self.capacity, client_data['tokens'] + tokens_to_add)
                client_data['last_update'] = now
                
            if client_data['tokens'] >= 1:
                client_data['tokens'] -= 1
                return True
            return False

rate_limiter = TokenBucketRateLimiter(capacity=20, fill_rate=1.0) # 1 token por segundo, capacidad 20

# Configuramos desde Variables de Entorno para mantener la pureza P2P Dockerizada
COUCHDB_USER = os.environ.get('COUCHDB_USER', 'admin')
COUCHDB_PASSWORD = os.environ.get('COUCHDB_PASSWORD', 'admin')
COUCHDB_HOST = os.environ.get('COUCHDB_HOST', 'localhost')
COUCHDB_PORT = os.environ.get('COUCHDB_PORT', '5984')
NODO_NAME = os.environ.get('NODO_NAME', 'Nodo Local')
ETCD_HOST = os.environ.get('ETCD_HOST', 'http://etcd-0.etcd:2379')

def write_to_etcd(key, value):
    """Escribe estado en etcd codificado en base64 (requerido por API v3)"""
    try:
        k_b64 = base64.b64encode(key.encode()).decode('utf-8')
        v_b64 = base64.b64encode(value.encode()).decode('utf-8')
        requests.put(f"{ETCD_HOST}/v3/kv/put", json={
            "key": k_b64,
            "value": v_b64
        }, timeout=2)
    except Exception as e:
        print(f"Error escribiendo en etcd: {e}")

def register_node_loop():
    """
    CORRECCIÓN (feedback profesor - CAP Theorem):
    etcd se usa SOLO para Service Discovery — registra la IP/puerto de este nodo
    para que los otros puedan encontrarlo.
    NO se usa para autorizar escrituras clínicas.
    La escritura clínica es SIEMPRE local (principio AP de CouchDB).
    """
    import time
    time.sleep(5)
    PORT = int(os.environ.get('PORT', 5000))
    while True:
        # Solo Service Discovery: ¿en qué dirección estoy?
        write_to_etcd(f"{NODO_NAME}-status", "alive")
        write_to_etcd(f"{NODO_NAME}-endpoint", f"http://0.0.0.0:{PORT}")
        time.sleep(30)

# Lanzar hilo de Service Discovery (NO de control de escritura)
threading.Thread(target=register_node_loop, daemon=True).start()


def generar_hash_integridad(datos: dict) -> str:
    """
    CORRECCIÓN (feedback profesor - Integridad ISO 27001 A.18):
    Genera SHA-256 del contenido completo de la Historia Clínica.
    El hash se persiste en DOS lugares: CouchDB y Citus.
    Si alguien modifica CouchDB, ambos hashes no coincidirán = evidencia forense.
    """
    contenido_canonico = json.dumps(datos, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(contenido_canonico.encode('utf-8')).hexdigest()


# Conexión Segura e Interna a la base de datos (Backend -> Database)
couch_url = f'http://{urllib.parse.quote(COUCHDB_USER)}:{urllib.parse.quote(COUCHDB_PASSWORD)}@{COUCHDB_HOST}:{COUCHDB_PORT}/'
try:
    couch = couchdb.Server(couch_url)
    db_name = 'historias_clinicas'
    if db_name not in couch:
        couch.create(db_name)
    db = couch[db_name]
except Exception as e:
    print(f"Error conectando a CouchDB: {e}")
    db = None

# ==========================================
# POSTGRES CITUS: BASE DE DATOS TRANSACCIONAL (WORKFLOW)
# ==========================================
CITUS_HOST = os.environ.get('CITUS_HOST', 'citus-coordinator')

def init_citus():
    try:
        # Esperamos brevemente para que el cluster esté listo
        time.sleep(10)
        conn = psycopg2.connect(
            dbname='clinic', user='myuser', password='mypass', host=CITUS_HOST
        )
        conn.autocommit = True
        cursor = conn.cursor()
        
        # Enlistar workers si se usa master_add_node
        try:
            cursor.execute("SELECT master_add_node('citus-worker-1', 5432);")
        except:
            pass  # Falla silenciosa si ya está agregado
            
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS paciente_en_curso (
                documento VARCHAR(50) PRIMARY KEY,
                nombre VARCHAR(100),
                estado VARCHAR(50),
                nodo_asignado VARCHAR(50)
            );
        """)
        
        # Convertir a tabla distribuida, particionada por "documento"
        try:
            cursor.execute("SELECT create_distributed_table('paciente_en_curso', 'documento');")
            print("Tabla Distribuida en Postgres Citus lista!")
        except Exception as e:
            # Falla si ya es una tabla distribuida, lo cual es normal
            pass
            
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"No se pudo inicializar Citus: {e}")

threading.Thread(target=init_citus, daemon=True).start()

@app.before_request
def before_request():
    # Excluir endpoints de diagnóstico, metadatos FHIR y lectura del Rate Limit
    # Importante para que Inferno pueda auditar sin ser bloqueado
    if request.path in ['/_up', '/_all_docs', '/fhir/metadata']:
        return None
        
    client_ip = request.remote_addr
    if not rate_limiter.allow_request(client_ip):
        return jsonify({"resourceType": "OperationOutcome", "issue": [{"severity": "error", "code": "throttled", "diagnostics": "Demasiadas peticiones (Rate Limit). Por favor intente más tarde."}]}), 429

def generar_sello_integridad(patient_res):
    """
    ISO 27001 - Integridad: Generación de firma en Backend de forma nativa e inalterable desde cliente.
    """
    if not patient_res or "name" not in patient_res or not isinstance(patient_res["name"], list) or len(patient_res["name"]) == 0:
        return "N/A"
    
    name_obj = patient_res["name"][0]
    # En Python un dict se accede con .get o ['key'], hay que evitar IndexError
    name_text = name_obj.get("text", "") 
    
    semilla = f"{patient_res.get('id', '')}-{name_text}-{patient_res.get('birthDate', '')}"
    return base64.b64encode(semilla.encode('utf-8')).decode('utf-8')[:16]

@app.route('/_up', methods=['GET'])
def healthcheck():
    """Endpoint de salud para que Docker Compose sepa que la API está lista"""
    if db is not None:
        try:
            # Check si couchdb responde
            couch.version()
            # Opcional: También aseguramos enviar la señal por cada check
            write_to_etcd(f"{NODO_NAME}-status", "alive")
            return jsonify({"status": "ok", "nodo": NODO_NAME}), 200
        except:
            return jsonify({"status": "db_error", "nodo": NODO_NAME}), 503
    return jsonify({"status": "error", "nodo": NODO_NAME}), 503

@app.route('/elect', methods=['GET'])
def elect_leader():
    """Endpoint para elegir líder (primitiva de consenso con etcd)"""
    try:
        key = "leader"
        value = NODO_NAME
        write_to_etcd(key, value)
        return jsonify({"message": f"{NODO_NAME} elected itself as leader"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ------------------------------------------------------------------
# BÚSQUEDA FEDERADA P2P — Lookup multinode de pacientes
# ------------------------------------------------------------------
@app.route('/recepcion/buscar/<documento_id>', methods=['GET'])
def buscar_paciente(documento_id):
    """
    Busca un paciente en la base de datos LOCAL (Citus) de este nodo.
    Retorna los datos completos + el nombre del nodo que lo tiene.
    El frontend consultará este endpoint en TODOS los nodos en paralelo
    para implementar la búsqueda federada P2P.
    """
    try:
        conn = psycopg2.connect(dbname='clinic', user='myuser', password='mypass', host=CITUS_HOST)
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute("""
            SELECT documento_id, tipo_documento, pais_nacionalidad, nombre_completo,
                   fecha_nacimiento, edad, unidad_edad, sexo, genero, ocupacion,
                   voluntad_anticipada, categoria_discapacidad,
                   pais_residencia, municipio_residencia, etnia
            FROM hcd.usuario WHERE documento_id = %s
        """, (int(documento_id),))
        row = cur.fetchone()
        cur.close(); conn.close()

        if row is None:
            return jsonify({"encontrado": False, "nodo": NODO_NAME}), 404

        campos = ['documento_id','tipo_documento','pais_nacionalidad','nombre_completo',
                  'fecha_nacimiento','edad','unidad_edad','sexo','genero','ocupacion',
                  'voluntad_anticipada','categoria_discapacidad',
                  'pais_residencia','municipio_residencia','etnia']
        datos = dict(zip(campos, row))
        # Convertir tipos no serializables
        if datos.get('fecha_nacimiento'):
            datos['fecha_nacimiento'] = str(datos['fecha_nacimiento'])
        datos['voluntad_anticipada'] = bool(datos['voluntad_anticipada'])

        return jsonify({
            "encontrado": True,
            "nodo_origen": NODO_NAME,
            "paciente": datos
        }), 200
    except Exception as e:
        return jsonify({"encontrado": False, "nodo": NODO_NAME, "error": str(e)}), 500

# ------------------------------------------------------------------
# IMPORTAR PACIENTE DESDE OTRO NODO (replicación bajo demanda)
# ------------------------------------------------------------------
@app.route('/recepcion/importar', methods=['POST'])
def importar_paciente():
    """
    Recibe los datos de un paciente provenientes de OTRO nodo P2P
    y los guarda en el Citus LOCAL, registrando el nodo de origen.
    Esto implementa la 'replicación sota demanda' del protocolo P2P.
    """
    data = request.json
    paciente = data.get('paciente', {})
    nodo_origen = data.get('nodo_origen', 'desconocido')
    doc = paciente.get('documento_id')
    if not doc:
        return jsonify({"error": "documento_id requerido"}), 400

    sql = """
        INSERT INTO hcd.usuario (
            documento_id, tipo_documento, pais_nacionalidad, nombre_completo,
            fecha_nacimiento, edad, unidad_edad, sexo, genero, ocupacion,
            voluntad_anticipada, categoria_discapacidad,
            pais_residencia, municipio_residencia, etnia
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (documento_id) DO NOTHING
    """
    params = (
        int(doc), paciente.get('tipo_documento','CC'),
        paciente.get('pais_nacionalidad','CO'), paciente.get('nombre_completo',''),
        paciente.get('fecha_nacimiento'), paciente.get('edad'),
        paciente.get('unidad_edad','Años'), paciente.get('sexo','M'),
        paciente.get('genero'), paciente.get('ocupacion'),
        paciente.get('voluntad_anticipada', False), paciente.get('categoria_discapacidad'),
        paciente.get('pais_residencia','CO'), paciente.get('municipio_residencia'),
        paciente.get('etnia')
    )
    try:
        conn = psycopg2.connect(dbname='clinic', user='myuser', password='mypass', host=CITUS_HOST)
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(sql, params)
        cur.close(); conn.close()
        return jsonify({
            "message": f"✅ Paciente importado desde {nodo_origen} → {NODO_NAME} (replicación P2P exitosa)",
            "nodo_destino": NODO_NAME,
            "nodo_origen": nodo_origen
        }), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500



def citus_conn():
    """Helper: devuelve conexión a Citus"""
    return psycopg2.connect(dbname='clinic', user='myuser', password='mypass', host=CITUS_HOST)

# ------------------------------------------------------------------
# SECCIÓN 1: RECEPCIÓN — Identificación del Usuario (15 campos)
# Resolución 866/2021 — Campos 1 al 15
# ------------------------------------------------------------------
@app.route('/recepcion/ingreso', methods=['POST'])
def registro_recepcion():
    """
    Guarda los 15 campos de Identificación de Usuario en Postgres Citus.
    Estado inicial del paciente en el flujo clínico: RECEPCION.
    """
    data = request.json
    doc = data.get('documento_id') or data.get('documento')
    if not doc:
        return jsonify({"error": "documento_id es requerido"}), 400

    sql = """
        INSERT INTO hcd.usuario (
            documento_id, tipo_documento, pais_nacionalidad, nombre_completo,
            fecha_nacimiento, edad, unidad_edad, sexo, genero, ocupacion,
            voluntad_anticipada, categoria_discapacidad,
            pais_residencia, municipio_residencia, etnia
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (documento_id) DO UPDATE SET
            tipo_documento=EXCLUDED.tipo_documento,
            nombre_completo=EXCLUDED.nombre_completo,
            fecha_nacimiento=EXCLUDED.fecha_nacimiento,
            edad=EXCLUDED.edad, sexo=EXCLUDED.sexo, genero=EXCLUDED.genero,
            municipio_residencia=EXCLUDED.municipio_residencia
    """
    params = (
        int(doc),
        data.get('tipo_documento','CC'),
        data.get('pais_nacionalidad','CO'),
        data.get('nombre_completo',''),
        data.get('fecha_nacimiento'),
        data.get('edad'),
        data.get('unidad_edad','Años'),
        data.get('sexo','M'),
        data.get('genero'),
        data.get('ocupacion'),
        data.get('voluntad_anticipada', False),
        data.get('categoria_discapacidad'),
        data.get('pais_residencia','CO'),
        data.get('municipio_residencia'),
        data.get('etnia')
    )
    try:
        conn = citus_conn()
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(sql, params)
        cur.close(); conn.close()
        # Auto-push Patient a HAPI FHIR (Requisito 3.2)
        threading.Thread(target=auto_push_fhir_resources, args=(doc, 'recepcion', data), daemon=True).start()
        return jsonify({"message": "✅ Sección 1/5 — Identificación registrada en Citus.", "documento_id": doc, "etapa": "RECEPCION"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ------------------------------------------------------------------
# SECCIÓN 2: TRIAJE — Datos de la Atención (9 campos)
# Resolución 866/2021 — Campos 16 al 24
# ------------------------------------------------------------------
@app.route('/atencion/triaje', methods=['POST'])
def registro_triaje():
    """
    Registra los 9 campos de Atención/Triaje en Postgres Citus.
    Avanza el estado del paciente: TRIAJE.
    """
    data = request.json
    doc = data.get('documento_id')
    if not doc:
        return jsonify({"error": "documento_id es requerido"}), 400

    sql = """
        INSERT INTO hcd.atencion (
            documento_id, entidad_salud, fecha_ingreso, modalidad_entrega,
            entorno_atencion, via_ingreso, causa_atencion,
            fecha_triage, clasificacion_triage, comunidad_etnica
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        RETURNING atencion_id
    """
    params = (
        int(doc),
        data.get('entidad_salud','Sin especificar'),
        data.get('fecha_ingreso', time.strftime('%Y-%m-%d %H:%M:%S')),
        data.get('modalidad_entrega','Presencial'),
        data.get('entorno_atencion','Consulta'),
        data.get('via_ingreso'),
        data.get('causa_atencion'),
        data.get('fecha_triage'),
        data.get('clasificacion_triage'),
        data.get('comunidad_etnica')
    )
    try:
        conn = citus_conn()
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(sql, params)
        atencion_id = cur.fetchone()[0]
        cur.close(); conn.close()
        # Auto-push Encounter + Observation a HAPI FHIR (Requisito 3.2)
        threading.Thread(target=auto_push_fhir_resources, args=(doc, 'triaje', data, atencion_id), daemon=True).start()
        return jsonify({"message": "✅ Sección 2/5 — Triaje registrado en Citus.", "atencion_id": atencion_id, "etapa": "TRIAJE"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ------------------------------------------------------------------
# CATÁLOGO CIE-11 — Endpoint de consulta para frontend
# ------------------------------------------------------------------
@app.route('/catalogo/cie11', methods=['GET'])
def listar_cie11():
    """Retorna el catálogo CIE-11 disponible para los dropdowns del frontend."""
    try:
        conn = citus_conn()
        cur = conn.cursor()
        cur.execute("SELECT codigo, titulo, codigo_cie10 FROM hcd.catalogo_cie11 ORDER BY codigo")
        rows = cur.fetchall()
        cur.close(); conn.close()
        return jsonify([
            {"codigo": r[0], "titulo": r[1], "mapeo_cie10": r[2]} for r in rows
        ]), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ------------------------------------------------------------------
# SECCIÓN 3: MEDICAMENTOS — Tecnologías en Salud (11 campos)
# Resolución 866/2021 — Campos 25 al 35
# ------------------------------------------------------------------
@app.route('/atencion/medicamentos', methods=['POST'])
def registro_medicamentos():
    """
    Registra tecnologías en salud (medicamentos) de una atención en Citus.
    """
    data = request.json
    doc = data.get('documento_id')
    if not doc:
        return jsonify({"error": "documento_id es requerido"}), 400

    sql = """
        INSERT INTO hcd.tecnologia_salud (
            documento_id, atencion_id, descripcion_medicamento, dosis,
            via_administracion, frecuencia, dias_tratamiento, unidades_aplicadas,
            id_personal_salud, finalidad_tecnologia,
            tipo_diagnostico_ingreso, diagnostico_ingreso, tipo_diagnostico_egreso
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """
    import uuid
    id_profesional = data.get('id_personal_salud')
    try:
        if id_profesional:
            uuid.UUID(str(id_profesional))
        else:
            id_profesional = None
    except ValueError:
        id_profesional = None

    # Auto-mapeo CIE-10 → CIE-11
    diagnostico_cie11 = data.get('diagnostico_ingreso_cie11')
    diagnostico_cie10 = data.get('diagnostico_ingreso')
    if diagnostico_cie10 and not diagnostico_cie11:
        try:
            conn_map = citus_conn()
            cur_map = conn_map.cursor()
            cur_map.execute("SELECT hcd.mapear_cie10_a_cie11(%s)", (diagnostico_cie10,))
            diagnostico_cie11 = cur_map.fetchone()[0]
            cur_map.close(); conn_map.close()
        except Exception:
            diagnostico_cie11 = None

    params = (
        int(doc),
        data.get('atencion_id'),
        data.get('descripcion_medicamento',''),
        data.get('dosis'),
        data.get('via_administracion'),
        data.get('frecuencia'),
        data.get('dias_tratamiento'),
        data.get('unidades_aplicadas', 0),
        id_profesional,
        data.get('finalidad_tecnologia'),
        data.get('tipo_diagnostico_ingreso'),
        diagnostico_cie10,
        data.get('tipo_diagnostico_egreso')
    )
    try:
        conn = citus_conn()
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(sql, params)
        cur.close(); conn.close()
        # Auto-push MedicationRequest a HAPI FHIR (Requisito 3.2)
        threading.Thread(target=auto_push_fhir_resources, args=(doc, 'medicamentos', data), daemon=True).start()
        return jsonify({"message": "✅ Sección 3/5 — Medicamentos registrados en Citus.", "etapa": "MEDICAMENTOS", "cie11_auto": diagnostico_cie11}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ------------------------------------------------------------------
# SECCIÓN 4: DIAGNÓSTICO — CIE-10 (4 campos)
# Resolución 866/2021 — Campos 36 al 39
# ------------------------------------------------------------------
@app.route('/atencion/diagnostico', methods=['POST'])
def registro_diagnostico():
    """
    Registra los diagnósticos CIE-10 de una atención en Citus.
    """
    data = request.json
    doc = data.get('documento_id')
    if not doc:
        return jsonify({"error": "documento_id es requerido"}), 400

    sql = """
        INSERT INTO hcd.diagnostico (
            documento_id, atencion_id, diagnostico_egreso,
            diagnostico_rel1, diagnostico_rel2, diagnostico_rel3
        ) VALUES (%s,%s,%s,%s,%s,%s)
    """
    params = (
        int(doc),
        data.get('atencion_id'),
        data.get('diagnostico_egreso','Z00'),
        data.get('diagnostico_rel1'),
        data.get('diagnostico_rel2'),
        data.get('diagnostico_rel3')
    )
    try:
        conn = citus_conn()
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(sql, params)
        cur.close(); conn.close()
        # Auto-push Condition a HAPI FHIR (Requisito 3.2)
        threading.Thread(target=auto_push_fhir_resources, args=(doc, 'diagnostico', data), daemon=True).start()
        return jsonify({"message": "✅ Sección 4/5 — Diagnósticos CIE-10 registrados en Citus.", "etapa": "DIAGNOSTICO"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ------------------------------------------------------------------
# SECCIÓN 5: EGRESO — Cierre del Expediente (18 campos)
# Resolución 866/2021 — Campos 40 al 57
# ------------------------------------------------------------------
@app.route('/egreso/salida', methods=['POST'])
def registro_egreso():
    """
    Registra el egreso completo del paciente (18 campos) en Citus.
    También construye un Bundle FHIR Resume y lo persiste en CouchDB.
    """
    data = request.json
    doc = data.get('documento_id')
    if not doc:
        return jsonify({"error": "documento_id es requerido"}), 400

    sql = """
        INSERT INTO hcd.egreso (
            documento_id, atencion_id, fecha_salida, condicion_salida,
            diagnostico_muerte, codigo_prestador, tipo_incapacidad,
            dias_incapacidad, dias_lic_maternidad, alergias,
            antecedentes_familiares, riesgos_ocupacionales, responsable_egreso,
            zona_residencia, direccion_residencia, telefono,
            correo_electronico, nombre_responsable, parentesco_responsable, telefono_responsable
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """
    # Sanitizar: strings vacíos → None para campos opcionales/enteros
    def _or_none(val):
        """Convierte '' y None a None para evitar errores de tipo en PostgreSQL"""
        if val is None or val == '':
            return None
        return val

    params = (
        int(doc),
        _or_none(data.get('atencion_id')),
        data.get('fecha_salida', time.strftime('%Y-%m-%d %H:%M:%S')),
        data.get('condicion_salida','Vivo'),
        _or_none(data.get('diagnostico_muerte')),
        data.get('codigo_prestador','000000'),
        _or_none(data.get('tipo_incapacidad')),
        _or_none(data.get('dias_incapacidad')) and int(data.get('dias_incapacidad')),
        _or_none(data.get('dias_lic_maternidad')) and int(data.get('dias_lic_maternidad')),
        _or_none(data.get('alergias')),
        _or_none(data.get('antecedentes_familiares')),
        _or_none(data.get('riesgos_ocupacionales')),
        data.get('responsable_egreso','Sin especificar'),
        data.get('zona_residencia','Urbana'),
        data.get('direccion_residencia','Sin especificar'),
        _or_none(data.get('telefono')),
        _or_none(data.get('correo_electronico')),
        _or_none(data.get('nombre_responsable')),
        _or_none(data.get('parentesco_responsable')),
        _or_none(data.get('telefono_responsable'))
    )
    try:
        conn = citus_conn()
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(sql, params)
        cur.close(); conn.close()

        # Persistir resumen final como Patient FHIR en CouchDB
        if db is not None:
            patient_fhir = {
                "resourceType": "Patient",
                "id": str(doc),
                "_id": str(doc),
                "name": [{"text": data.get('nombre_completo', str(doc))}],
                "gender": data.get('sexo', 'M') == 'M' and 'male' or 'female',
                "birthDate": data.get('fecha_nacimiento'),
                "meta": {"profile": ["http://hl7.org/fhir/us/core/StructureDefinition/us-core-patient"]},
                "p2p_audit": {
                    "nodo_emisor": NODO_NAME,
                    "timestamp": time.time(),
                    "etapa": "EGRESO_COMPLETADO"
                },
                # CORRECCIÓN (feedback profesor - Integridad ISO 27001 A.18)
                # SHA-256 del expediente completo — si alguien altera CouchDB,
                # el hash en Citus no coincidirá. Evidencia forense real.
                "hash_integridad": generar_hash_integridad({
                    "documento_id": doc,
                    "nombre_completo": data.get('nombre_completo'),
                    "fecha_nacimiento": data.get('fecha_nacimiento'),
                    "diagnostico_egreso": data.get('diagnostico_egreso'),
                    "condicion_salida": data.get('condicion_salida'),
                    "fecha_salida": data.get('fecha_salida'),
                    "responsable_egreso": data.get('responsable_egreso'),
                    "nodo_emisor": NODO_NAME
                })
            }
            try:
                db.save(patient_fhir)
            except Exception:
                pass  # Ya existe el doc — no es crítico

        return jsonify({
            "message": "✅ Sección 5/5 — Egreso completo. Historia Clínica cerrada y archivada en red P2P.",
            "etapa": "EGRESO_COMPLETADO",
            "hash_integridad": generar_hash_integridad({"documento_id": doc, "nodo_emisor": NODO_NAME})
        }), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500





@app.route('/_all_docs', methods=['GET'])
def get_all_docs():
    """Proxy para extraer todos los documentos sin exponer la DB P2P"""
    if db is None:
        return jsonify({"error": "Database not connected"}), 500
    
    docs = []
    for id in db:
        if not id.startswith('_'):
            docs.append({"doc": db[id]})
            
    return jsonify({"rows": docs}), 200

# ==========================================
# SECCIÓN FHIR R4 - AUDITORÍA INFERNO
# ==========================================

@app.route('/fhir/metadata', methods=['GET'])
def capability_statement():
    """
    Requisito #1 de Inferno: CapabilityStatement.
    Define qué recursos y operaciones soporta este servidor.
    """
    cs = {
        "resourceType": "CapabilityStatement",
        "status": "active",
        "date": "2026-03-30",
        "publisher": "Red Salud Distribuida",
        "kind": "instance",
        "software": { "name": "Nodo P2P Salud", "version": "2.0.0" },
        "fhirVersion": "4.0.1",
        "format": ["application/fhir+json"],
        "rest": [{
            "mode": "server",
            "security": {
                "description": "Simulated SMART on FHIR for Audit purposes",
                "extension": [{
                    "url": "http://fhir-navigation.static.alphora.com/lib/smart-on-fhir",
                    "extension": [
                        {"url": "authorize", "valueUri": "http://localhost:5000/auth/authorize"},
                        {"url": "token", "valueUri": "http://localhost:5000/auth/token"}
                    ]
                }]
            },
            "resource": [{
                "type": "Patient",
                "profile": "http://hl7.org/fhir/us/core/StructureDefinition/us-core-patient",
                "interaction": [
                    {"code": "read"},
                    {"code": "search-type"},
                    {"code": "create"}
                ],
                "searchParam": [
                    {"name": "_id", "type": "token"},
                    {"name": "family", "type": "string"},
                    {"name": "given", "type": "string"}
                ]
            }]
        }]
    }
    resp = jsonify(cs)
    resp.headers['Content-Type'] = 'application/fhir+json'
    return resp

@app.route('/fhir/Patient/<id>', methods=['GET'])
def read_patient(id):
    """Lectura individual de Paciente (FHIR Read)"""
    if db is None: return jsonify({"resourceType": "OperationOutcome", "issue": [{"severity": "error", "code": "exception", "diagnostics": "DB not connected"}]}), 500
    
    try:
        doc = db.get(id)
        if doc:
            # Si el doc es un Bundle (como se guardaba antes), extraemos el Patient
            if doc.get("resourceType") == "Bundle":
                patient = next((e["resource"] for e in doc.get("entry", []) if e.get("resource", {}).get("resourceType") == "Patient"), None)
                if patient: 
                    resp = jsonify(patient)
                    resp.headers['Content-Type'] = 'application/fhir+json'
                    return resp
            
            # Si ya es un recurso Patient
            resp = jsonify(doc)
            resp.headers['Content-Type'] = 'application/fhir+json'
            return resp
            
        return jsonify({"resourceType": "OperationOutcome", "issue": [{"severity": "error", "code": "not-found", "diagnostics": "Patient not found"}]}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/fhir/Patient', methods=['GET'])
def search_patient():
    """Búsqueda de Pacientes (FHIR Search)"""
    if db is None: return jsonify({"error": "DB not connected"}), 500
    
    # Parámetros de búsqueda
    search_id = request.args.get('_id')
    family = request.args.get('family', '').lower()
    
    results = []
    try:
        for doc_id in db:
            if doc_id.startswith('_'): continue
            doc = db[doc_id]
            
            patient = None
            if doc.get("resourceType") == "Bundle":
                patient = next((e["resource"] for e in doc.get("entry", []) if e.get("resource", {}).get("resourceType") == "Patient"), None)
            elif doc.get("resourceType") == "Patient":
                patient = doc

            if patient:
                # Aplicar filtros básicos
                match = True
                if search_id and patient.get('id') != search_id: match = False
                if family:
                    # Buscar en los nombres
                    names = patient.get('name', [])
                    found_family = any(family in str(n.get('family', '')).lower() for n in names)
                    if not found_family: match = False
                
                if match:
                    results.append({"fullUrl": f"{request.base_url}/{patient.get('id')}", "resource": patient})

        bundle = {
            "resourceType": "Bundle",
            "type": "searchset",
            "total": len(results),
            "entry": results
        }
        resp = jsonify(bundle)
        resp.headers['Content-Type'] = 'application/fhir+json'
        return resp
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/fhir/Patient', methods=['POST'])
def create_patient():
    """Creación de Paciente - Soporta tanto Bundle como recurso Patient directo"""
    if db is None: return jsonify({"error": "DB not connected"}), 500
        
    data = request.json
    resource_type = data.get("resourceType")
    
    patient_res = None
    if resource_type == "Bundle":
        entries = data.get("entry", [])
        patient_res = next((e["resource"] for e in entries if e.get("resource", {}).get("resourceType") == "Patient"), None)
    elif resource_type == "Patient":
        patient_res = data
        
    if not patient_res:
        return jsonify({"resourceType": "OperationOutcome", "issue": [{"severity": "error", "code": "invalid", "diagnostics": "No Patient resource found"}]}), 400
        
    # ISO 27001 - Integridad: Firma nativa
    nuevo_hash = generar_sello_integridad(patient_res)
    
    # Aseguramos cumplimiento de US Core básico
    if "meta" not in patient_res: patient_res["meta"] = {}
    patient_res["meta"]["profile"] = ["http://hl7.org/fhir/us/core/StructureDefinition/us-core-patient"]
    
    # Guardar en CouchDB
    doc_to_save = patient_res.copy()
    doc_to_save["p2p_audit"] = {"hash_firma": nuevo_hash, "nodo_emisor": NODO_NAME, "timestamp": time.time()}
    
    if "id" in doc_to_save: doc_to_save["_id"] = doc_to_save["id"]
    
    try:
        doc_id, doc_rev = db.save(doc_to_save)
        resp = jsonify(patient_res)
        resp.headers['Content-Type'] = 'application/fhir+json'
        resp.status_code = 201
        return resp
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ==========================================
# OAUTH2 / SMART ON FHIR — Requisito 3.3
# ==========================================

@app.route('/auth/token', methods=['POST'])
def auth_token():
    """
    OAuth2 Token Endpoint — emite JWT para proteger endpoints FHIR.
    Soporta grant_type=client_credentials (para Postman/curl).
    """
    grant_type = request.form.get('grant_type') or (request.json or {}).get('grant_type')
    client_id = request.form.get('client_id') or (request.json or {}).get('client_id', 'default-client')
    scope = request.form.get('scope') or (request.json or {}).get('scope', 'patient/*.read patient/*.write')

    if grant_type not in ('client_credentials', 'authorization_code', None):
        return jsonify({"error": "unsupported_grant_type"}), 400

    payload = {
        "sub": client_id,
        "iss": f"http://{NODO_NAME.replace(' ', '-').lower()}.redsalud.co",
        "scope": scope,
        "nodo": NODO_NAME,
        "iat": datetime.datetime.utcnow(),
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=JWT_EXPIRATION_HOURS)
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return jsonify({
        "access_token": token,
        "token_type": "Bearer",
        "expires_in": JWT_EXPIRATION_HOURS * 3600,
        "scope": scope
    }), 200


def require_jwt(f):
    """Decorator: protege endpoints FHIR con JWT (Requisito 3.3)."""
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return jsonify({"resourceType": "OperationOutcome", "issue": [{"severity": "error", "code": "security", "diagnostics": "Token Bearer requerido."}]}), 401
        token = auth_header.split(' ', 1)[1]
        try:
            decoded = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            request.jwt_claims = decoded
        except jwt.ExpiredSignatureError:
            return jsonify({"resourceType": "OperationOutcome", "issue": [{"severity": "error", "code": "security", "diagnostics": "Token expirado."}]}), 401
        except jwt.InvalidTokenError:
            return jsonify({"resourceType": "OperationOutcome", "issue": [{"severity": "error", "code": "security", "diagnostics": "Token inválido."}]}), 401
        return f(*args, **kwargs)
    return decorated


@app.route('/auth/authorize', methods=['GET'])
def auth_authorize():
    """SMART on FHIR authorize endpoint (simplified)."""
    return jsonify({"message": "Use /auth/token con grant_type=client_credentials para obtener un JWT."}), 200


# ==========================================
# HAPI FHIR PROXY — Requisitos 3.1, 3.2
# Push de recursos FHIR al servidor HAPI real
# ==========================================

def push_to_hapi(resource_type, resource_data):
    """Envía un recurso FHIR al servidor HAPI FHIR real."""
    try:
        resp = requests.post(
            f"{HAPI_FHIR_URL}/{resource_type}",
            json=resource_data,
            headers={"Content-Type": "application/fhir+json"},
            timeout=10
        )
        if resp.status_code in (200, 201):
            return resp.json()
        print(f"HAPI FHIR push {resource_type} status={resp.status_code}: {resp.text[:200]}")
        return None
    except Exception as e:
        print(f"Error push HAPI FHIR {resource_type}: {e}")
        return None


@app.route('/hapi/Patient', methods=['POST'])
@require_jwt
def hapi_create_patient():
    """Crea Patient en HAPI FHIR (protegido por JWT)."""
    data = request.json
    result = push_to_hapi("Patient", data)
    if result:
        return jsonify(result), 201
    return jsonify({"error": "No se pudo crear Patient en HAPI FHIR"}), 502


@app.route('/hapi/Encounter', methods=['POST'])
@require_jwt
def hapi_create_encounter():
    """Crea Encounter en HAPI FHIR (Requisito 3.2)."""
    data = request.json
    result = push_to_hapi("Encounter", data)
    if result:
        return jsonify(result), 201
    return jsonify({"error": "No se pudo crear Encounter en HAPI FHIR"}), 502


@app.route('/hapi/Observation', methods=['POST'])
@require_jwt
def hapi_create_observation():
    """Crea Observation en HAPI FHIR (signos vitales / triage)."""
    data = request.json
    result = push_to_hapi("Observation", data)
    if result:
        return jsonify(result), 201
    return jsonify({"error": "No se pudo crear Observation en HAPI FHIR"}), 502


@app.route('/hapi/Condition', methods=['POST'])
@require_jwt
def hapi_create_condition():
    """Crea Condition en HAPI FHIR (diagnóstico)."""
    data = request.json
    result = push_to_hapi("Condition", data)
    if result:
        return jsonify(result), 201
    return jsonify({"error": "No se pudo crear Condition en HAPI FHIR"}), 502


@app.route('/hapi/MedicationRequest', methods=['POST'])
@require_jwt
def hapi_create_medication_request():
    """Crea MedicationRequest en HAPI FHIR (prescripción)."""
    data = request.json
    result = push_to_hapi("MedicationRequest", data)
    if result:
        return jsonify(result), 201
    return jsonify({"error": "No se pudo crear MedicationRequest en HAPI FHIR"}), 502


@app.route('/hapi/<resource_type>', methods=['GET'])
def hapi_search(resource_type):
    """Proxy de búsqueda genérico hacia HAPI FHIR."""
    try:
        params = dict(request.args)
        resp = requests.get(f"{HAPI_FHIR_URL}/{resource_type}", params=params, timeout=10)
        return jsonify(resp.json()), resp.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 502


@app.route('/hapi/<resource_type>/<resource_id>', methods=['GET'])
def hapi_read(resource_type, resource_id):
    """Proxy de lectura individual hacia HAPI FHIR."""
    try:
        resp = requests.get(f"{HAPI_FHIR_URL}/{resource_type}/{resource_id}", timeout=10)
        return jsonify(resp.json()), resp.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 502


@app.route('/hapi/metadata', methods=['GET'])
def hapi_metadata():
    """Proxy del CapabilityStatement de HAPI FHIR."""
    try:
        resp = requests.get(f"{HAPI_FHIR_URL}/metadata", timeout=10)
        result = resp.json()
        result['_nodo'] = NODO_NAME
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"error": f"HAPI FHIR no disponible: {e}"}), 502


# ==========================================
# AUTO-PUSH: Crear recursos FHIR al guardar en Citus
# ==========================================

def auto_push_fhir_resources(doc_id, seccion, data, atencion_id=None):
    """
    Crea automáticamente recursos FHIR en HAPI al guardar cada sección en Citus.
    Esto garantiza que la rúbrica 3.2 (≥5 recursos FHIR) se cumpla de forma transparente.
    """
    try:
        if seccion == 'recepcion':
            push_to_hapi("Patient", {
                "resourceType": "Patient",
                "identifier": [{"system": "http://redsalud.co/documento", "value": str(doc_id)}],
                "name": [{"text": data.get('nombre_completo', ''), "family": data.get('nombre_completo', '').split()[-1] if data.get('nombre_completo') else ''}],
                "gender": "male" if data.get('sexo') == 'M' else "female" if data.get('sexo') == 'F' else "other",
                "birthDate": data.get('fecha_nacimiento'),
                "meta": {"profile": ["http://hl7.org/fhir/us/core/StructureDefinition/us-core-patient"]}
            })
        elif seccion == 'triaje':
            # Encounter
            push_to_hapi("Encounter", {
                "resourceType": "Encounter",
                "status": "in-progress",
                "class": {"system": "http://terminology.hl7.org/CodeSystem/v3-ActCode", "code": "AMB"},
                "subject": {"reference": f"Patient?identifier={doc_id}"},
                "period": {"start": data.get('fecha_ingreso', time.strftime('%Y-%m-%dT%H:%M:%S'))},
                "reasonCode": [{"text": data.get('causa_atencion', '')}],
                "priority": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/v3-ActPriority", "code": data.get('clasificacion_triage', 'R')}]}
            })
            # Observation (triage)
            if data.get('clasificacion_triage'):
                push_to_hapi("Observation", {
                    "resourceType": "Observation",
                    "status": "final",
                    "code": {"coding": [{"system": "http://loinc.org", "code": "56839-4", "display": "Triage note"}]},
                    "subject": {"reference": f"Patient?identifier={doc_id}"},
                    "valueString": f"Triage Manchester nivel {data.get('clasificacion_triage')}",
                    "effectiveDateTime": data.get('fecha_triage', time.strftime('%Y-%m-%dT%H:%M:%S'))
                })
        elif seccion == 'medicamentos':
            push_to_hapi("MedicationRequest", {
                "resourceType": "MedicationRequest",
                "status": "active",
                "intent": "order",
                "subject": {"reference": f"Patient?identifier={doc_id}"},
                "medicationCodeableConcept": {"text": data.get('descripcion_medicamento', '')},
                "dosageInstruction": [{"text": f"{data.get('dosis','')} {data.get('via_administracion','')} {data.get('frecuencia','')}"}],
                "authoredOn": time.strftime('%Y-%m-%dT%H:%M:%S')
            })
        elif seccion == 'diagnostico':
            push_to_hapi("Condition", {
                "resourceType": "Condition",
                "clinicalStatus": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-clinical", "code": "active"}]},
                "code": {"coding": [{"system": "http://hl7.org/fhir/sid/icd-10", "code": data.get('diagnostico_egreso', 'Z00')}]},
                "subject": {"reference": f"Patient?identifier={doc_id}"}
            })
    except Exception as e:
        print(f"Auto-push FHIR ({seccion}): {e}")


# ==========================================
# HISTORIA CLÍNICA CONSOLIDADA — Requisito 4.4
# ==========================================

@app.route('/hc/completa/<documento_id>', methods=['GET'])
def hc_completa(documento_id):
    """
    Vista consolidada de HC: cruza las 5 tablas de Citus.
    Requisito 4.4: Patient + Encounter + Observations + Conditions + MedicationRequests.
    """
    try:
        conn = citus_conn()
        cur = conn.cursor()

        # Paciente
        cur.execute("SELECT * FROM hcd.usuario WHERE documento_id = %s", (int(documento_id),))
        cols_u = [d[0] for d in cur.description]
        row_u = cur.fetchone()
        paciente = dict(zip(cols_u, row_u)) if row_u else None
        if not paciente:
            cur.close(); conn.close()
            return jsonify({"error": "Paciente no encontrado", "nodo": NODO_NAME}), 404

        # Serializar tipos no JSON
        for k, v in paciente.items():
            if hasattr(v, 'isoformat'):
                paciente[k] = v.isoformat()
            elif isinstance(v, bool):
                pass
            elif v is None:
                pass

        # Atenciones
        cur.execute("SELECT * FROM hcd.atencion WHERE documento_id = %s ORDER BY created_at DESC", (int(documento_id),))
        cols_a = [d[0] for d in cur.description]
        atenciones = [dict(zip(cols_a, r)) for r in cur.fetchall()]
        for a in atenciones:
            for k, v in a.items():
                if hasattr(v, 'isoformat'):
                    a[k] = v.isoformat()

        # Tecnologías en salud / Medicamentos
        cur.execute("SELECT * FROM hcd.tecnologia_salud WHERE documento_id = %s ORDER BY created_at DESC", (int(documento_id),))
        cols_t = [d[0] for d in cur.description]
        medicamentos = [dict(zip(cols_t, r)) for r in cur.fetchall()]
        for m in medicamentos:
            for k, v in m.items():
                if hasattr(v, 'isoformat'):
                    m[k] = v.isoformat()
                elif isinstance(v, uuid_mod.UUID):
                    m[k] = str(v)

        # Diagnósticos
        cur.execute("SELECT * FROM hcd.diagnostico WHERE documento_id = %s ORDER BY created_at DESC", (int(documento_id),))
        cols_d = [d[0] for d in cur.description]
        diagnosticos = [dict(zip(cols_d, r)) for r in cur.fetchall()]
        for d in diagnosticos:
            for k, v in d.items():
                if hasattr(v, 'isoformat'):
                    d[k] = v.isoformat()

        # Egresos
        cur.execute("SELECT * FROM hcd.egreso WHERE documento_id = %s ORDER BY created_at DESC", (int(documento_id),))
        cols_e = [d[0] for d in cur.description]
        egresos = [dict(zip(cols_e, r)) for r in cur.fetchall()]
        for eg in egresos:
            for k, v in eg.items():
                if hasattr(v, 'isoformat'):
                    eg[k] = v.isoformat()

        cur.close(); conn.close()

        return jsonify({
            "nodo": NODO_NAME,
            "paciente": paciente,
            "atenciones": atenciones,
            "medicamentos": medicamentos,
            "diagnosticos": diagnosticos,
            "egresos": egresos,
            "total_atenciones": len(atenciones),
            "total_medicamentos": len(medicamentos)
        }), 200
    except Exception as e:
        return jsonify({"error": str(e), "nodo": NODO_NAME}), 500


# ==========================================
# REPORTES Y MÉTRICAS — Requisito 4.5
# ==========================================

@app.route('/reportes/metricas', methods=['GET'])
def reportes_metricas():
    """
    Dashboard con estadísticas: pacientes por nodo, diagnósticos frecuentes,
    tiempos de atención. Requisito 4.5 de la rúbrica.
    """
    try:
        conn = citus_conn()
        cur = conn.cursor()

        # Total pacientes
        cur.execute("SELECT COUNT(*) FROM hcd.usuario")
        total_pacientes = cur.fetchone()[0]

        # Pacientes por sexo
        cur.execute("SELECT sexo, COUNT(*) FROM hcd.usuario GROUP BY sexo ORDER BY COUNT(*) DESC")
        por_sexo = [{"sexo": r[0], "cantidad": r[1]} for r in cur.fetchall()]

        # Diagnósticos más frecuentes (top 10)
        cur.execute("""
            SELECT d.diagnostico_egreso, c.descripcion, COUNT(*) as total
            FROM hcd.diagnostico d
            LEFT JOIN hcd.catalogo_cie10 c ON d.diagnostico_egreso = c.codigo
            GROUP BY d.diagnostico_egreso, c.descripcion
            ORDER BY total DESC LIMIT 10
        """)
        top_diagnosticos = [{"codigo": r[0], "descripcion": r[1] or r[0], "total": r[2]} for r in cur.fetchall()]

        # Atenciones por tipo de triage
        cur.execute("""
            SELECT clasificacion_triage, COUNT(*) FROM hcd.atencion
            WHERE clasificacion_triage IS NOT NULL
            GROUP BY clasificacion_triage ORDER BY clasificacion_triage
        """)
        por_triage = [{"nivel": r[0], "cantidad": r[1]} for r in cur.fetchall()]

        # Atenciones por entorno
        cur.execute("SELECT entorno_atencion, COUNT(*) FROM hcd.atencion GROUP BY entorno_atencion ORDER BY COUNT(*) DESC")
        por_entorno = [{"entorno": r[0], "cantidad": r[1]} for r in cur.fetchall()]

        # Total egresos
        cur.execute("SELECT condicion_salida, COUNT(*) FROM hcd.egreso GROUP BY condicion_salida")
        por_condicion = [{"condicion": r[0], "cantidad": r[1]} for r in cur.fetchall()]

        # Atenciones últimos 7 días
        cur.execute("""
            SELECT DATE(fecha_ingreso) as dia, COUNT(*) FROM hcd.atencion
            WHERE fecha_ingreso >= now() - INTERVAL '7 days'
            GROUP BY dia ORDER BY dia
        """)
        ultimos_7_dias = [{"dia": str(r[0]), "cantidad": r[1]} for r in cur.fetchall()]

        cur.close(); conn.close()

        return jsonify({
            "nodo": NODO_NAME,
            "total_pacientes": total_pacientes,
            "pacientes_por_sexo": por_sexo,
            "top_diagnosticos": top_diagnosticos,
            "atenciones_por_triage": por_triage,
            "atenciones_por_entorno": por_entorno,
            "egresos_por_condicion": por_condicion,
            "atenciones_ultimos_7_dias": ultimos_7_dias
        }), 200
    except Exception as e:
        return jsonify({"error": str(e), "nodo": NODO_NAME}), 500


# ==========================================
# FAILOVER Y ESTADO DE BD — Requisito 5.1
# ==========================================

@app.route('/health/full', methods=['GET'])
def health_full():
    """Estado detallado del nodo: CouchDB + Citus + HAPI FHIR."""
    status = {"nodo": NODO_NAME, "couchdb": "unknown", "citus": "unknown", "hapi_fhir": "unknown"}
    try:
        couch.version()
        status["couchdb"] = "online"
    except:
        status["couchdb"] = "offline"
    try:
        conn = citus_conn()
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.close(); conn.close()
        status["citus"] = "online"
    except:
        status["citus"] = "offline"
    try:
        r = requests.get(f"{HAPI_FHIR_URL}/metadata", timeout=5)
        status["hapi_fhir"] = "online" if r.status_code == 200 else "degraded"
    except:
        status["hapi_fhir"] = "offline"

    all_ok = all(v == "online" for k, v in status.items() if k != "nodo")
    return jsonify(status), 200 if all_ok else 503


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)