import React, { useState, useEffect } from 'react';
import './App.css';

// ==========================================
// PISO 1: CONFIGURACIÓN Y EL NOTARIO (Fuera de App)
// ==========================================
const host = window.location.hostname;
const SEDES = [
  { nombre: 'La Guajira', url: `http://${host}:5000` },
  { nombre: 'Amazonas', url: `http://${host}:5001` },
  { nombre: 'Guainía', url: `http://${host}:5002` },
  { nombre: 'Nariño', url: `http://${host}:5003` }
];

// Validación visual en cliente, pero la integridad real es enforceada en Backend.
const generarSelloIntegridad = (res) => {
  if (!res || !res.name) return "N/A";
  const semilla = `${res.id}-${res.name[0]?.text}-${res.birthDate}`;
  return btoa(semilla).substring(0, 16);
};
// UBICACIÓN: Dentro de 'function App()', cerca de handleSubmit
const exportarJSON = (doc) => {
  const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(doc, null, 2));
  const downloadAnchorNode = document.createElement('a');
  downloadAnchorNode.setAttribute("href", dataStr);
  downloadAnchorNode.setAttribute("download", `HC_${doc.id}.json`);
  document.body.appendChild(downloadAnchorNode);
  downloadAnchorNode.click();
  downloadAnchorNode.remove();
};
function App() {
  // ==========================================
  // PISO 2: LA MEMORIA (ESTADOS)
  // ==========================================
  const [paginaActual, setPaginaActual] = useState('recepcion');
  const [etapaHC, setEtapaHC] = useState(1); // 1=Recepcion, 2=Triaje, 3=Med, 4=Dx, 5=Egreso
  const [atencionId, setAtencionId] = useState(null);

  // =============================================
  // ESTADO COMPLETO — 57 CAMPOS (Resolución 866/2021)
  // =============================================
  // SECCIÓN 1: Identificación del Usuario (campos 1-15)
  const [seccion1, setSeccion1] = useState({
    documento_id: '', tipo_documento: 'CC', pais_nacionalidad: 'CO',
    nombre_completo: '', fecha_nacimiento: '', edad: '', unidad_edad: 'Años',
    sexo: 'M', genero: 'Masculino', ocupacion: '', voluntad_anticipada: false,
    categoria_discapacidad: '', pais_residencia: 'CO', municipio_residencia: '', etnia: ''
  });
  // SECCIÓN 2: Datos de la Atención/Triaje (campos 16-24)
  const [seccion2, setSeccion2] = useState({
    entidad_salud: '', fecha_ingreso: '', modalidad_entrega: 'Presencial',
    entorno_atencion: 'Consulta', via_ingreso: 'Espontáneo', causa_atencion: '',
    fecha_triage: '', clasificacion_triage: '', comunidad_etnica: ''
  });
  // Catálogo de profesionales de salud cargados desde la BD
  const PROFESIONALES_SALUD = [
    { id: 'aa7e532a-5b3a-4cbe-934a-d01a80e01b0f', nombre: 'Dra. Andrea Borrero Ruiz', especialidad: 'Medicina Interna' },
    { id: '7b114f06-b03c-4c63-b0dd-6eed82ff9e04', nombre: 'Dr. Luis Enrique Pineda', especialidad: 'Urgencias y Emergencias' },
    { id: '395385d8-87c4-4d66-9a61-19f11e688970', nombre: 'Enf. Camila Hoyos Salas', especialidad: 'Enfermería Clínica' },
    { id: '02bf23ad-b7b3-4dcf-9f9f-51ce1a14645a', nombre: 'Dr. Hernán Díaz Ospina', especialidad: 'Medicina General' },
  ];
  // SECCIÓN 3: Tecnologías en Salud / Medicamentos (campos 25-35)
  const [seccion3, setSeccion3] = useState({
    descripcion_medicamento: '', dosis: '', via_administracion: 'Oral',
    frecuencia: 'Cada 8 horas', dias_tratamiento: 1, unidades_aplicadas: 1,
    id_personal_salud: 'aa7e532a-5b3a-4cbe-934a-d01a80e01b0f',
    finalidad_tecnologia: 'Terapéutica',
    tipo_diagnostico_ingreso: 'Confirmado', diagnostico_ingreso: 'Z00', tipo_diagnostico_egreso: 'Confirmado'
  });
  // SECCIÓN 4: Diagnósticos CIE-10 (campos 36-39)
  const [seccion4, setSeccion4] = useState({
    diagnostico_egreso: 'Z00', diagnostico_rel1: '', diagnostico_rel2: '', diagnostico_rel3: ''
  });
  // SECCIÓN 5: Datos de Egreso (campos 40-57)
  const [seccion5, setSeccion5] = useState({
    fecha_salida: '', condicion_salida: 'Vivo', diagnostico_muerte: '',
    codigo_prestador: '', tipo_incapacidad: '', dias_incapacidad: '',
    dias_lic_maternidad: '', alergias: '', antecedentes_familiares: '',
    riesgos_ocupacionales: '', responsable_egreso: '', zona_residencia: 'Urbana',
    direccion_residencia: '', telefono: '', correo_electronico: '',
    nombre_responsable: '', parentesco_responsable: '', telefono_responsable: ''
  });

  const CIE10 = [
    { codigo: 'Z00', descripcion: 'Examen general (sin quejas)' },
    { codigo: 'J00', descripcion: 'Rinofaringitis aguda (resfriado)' },
    { codigo: 'J18.9', descripcion: 'Neumonía, no especificada' },
    { codigo: 'I10', descripcion: 'Hipertensión esencial' },
    { codigo: 'E11', descripcion: 'Diabetes mellitus tipo 2' },
    { codigo: 'E11.9', descripcion: 'Diabetes tipo 2 sin complicaciones' },
    { codigo: 'K29.7', descripcion: 'Gastritis, no especificada' },
    { codigo: 'M54.5', descripcion: 'Dolor lumbar' },
    { codigo: 'A09', descripcion: 'Diarrea de origen infeccioso' },
    { codigo: 'J45', descripcion: 'Asma' },
    { codigo: 'S06', descripcion: 'Traumatismo intracraneal' },
    { codigo: 'O80', descripcion: 'Parto único espontáneo' },
  ];

  // CIE-11: Catálogo y toggle
  const [usarCIE11, setUsarCIE11] = useState(false);
  const [catalogoCIE11, setCatalogoCIE11] = useState([]);

  // Estados globales de la app (red P2P, carga, mensajes)
  const [nodosSimulados, setNodosSimulados] = useState({});
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState(null);
  const [listaPacientes, setListaPacientes] = useState([]);
  const [sedeVisualizacion, setSedeVisualizacion] = useState(SEDES[0]);
  const [saludRed, setSaludRed] = useState({});
  const [tokens, setTokens] = useState(5);
  const [bloqueado, setBloqueado] = useState(false);
  const LIMIT_COOLDOWN = 30000;

  // Estado legado del formulario FHIR (pestaña Historia Clínica)
  const [paciente, setPaciente] = useState({
    tipoDocumento: 'CC', numeroDocumento: '', nombreCompleto: '', fechaNacimiento: '', sexo: 'M',
    eps: '', regimen: 'Contributivo', nivelSisben: 'A1', etnia: 'Ninguna', ocupacion: '',
    municipioResidencia: 'Corozal', direccion: '', telefono: '', email: '', zona: 'Urbana',
    rh: 'O+', alergias: 'Ninguna', discapacidad: 'Ninguna', antecedentes: '',
    responsable: '', telResponsable: '', parentesco: ''
  });


  useEffect(() => {
    const verificarSalud = async () => {
      const estados = {};
      for (const sede of SEDES) {
        if (nodosSimulados[sede.nombre]) { estados[sede.nombre] = 'offline'; continue; }
        try {
          const res = await fetch(`${sede.url}/_up`);
          estados[sede.nombre] = res.ok ? 'online' : 'offline';
        } catch { estados[sede.nombre] = 'offline'; }
      }
      setSaludRed(estados);
    };
    verificarSalud();
    const interval = setInterval(verificarSalud, 8000);
    return () => clearInterval(interval);
  }, [nodosSimulados]);

  // Cargar catálogo CIE-11 desde el nodo activo
  useEffect(() => {
    fetch(`${sedeVisualizacion.url}/catalogo/cie11`)
      .then(r => r.json())
      .then(data => { if (Array.isArray(data)) setCatalogoCIE11(data); })
      .catch(() => setCatalogoCIE11([]));
  }, [sedeVisualizacion]);

  useEffect(() => {
    const cargar = async () => {
      if (nodosSimulados[sedeVisualizacion.nombre]) { setListaPacientes([]); return; }
      try {
        // ACTUALIZACIÓN FHIR: Usamos el endpoint estándar de búsqueda
        const res = await fetch(`${sedeVisualizacion.url}/fhir/Patient`);
        const data = await res.json();
        // Los resultados de búsqueda vienen en un Bundle con un array 'entry'
        if (data.entry) {
          setListaPacientes(data.entry.map(e => e.resource));
        } else {
          setListaPacientes([]);
        }
      } catch (err) {
        console.error("Error cargando pacientes:", err);
        setListaPacientes([]);
      }
    };
    cargar();
  }, [sedeVisualizacion, saludRed, nodosSimulados]);

  // ==========================================
  // PISO 4: LOS MANEJADORES (LOGICA DE BOTONES)
  // ==========================================
  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    const setter = { s1: setSeccion1, s2: setSeccion2, s3: setSeccion3, s4: setSeccion4, s5: setSeccion5 }[e.target.dataset.sec];
    if (setter) setter(prev => ({ ...prev, [name]: type === 'checkbox' ? checked : value }));
  };
  const handleIngreso = (e) => handleChange(e);

  // ──────────────────────────────────────────
  // BÚSQUEDA FEDERADA P2P
  // ──────────────────────────────────────────
  const [busquedaDoc, setBusquedaDoc] = useState('');
  const [buscando, setBuscando] = useState(false);
  const [resultadoFederado, setResultadoFederado] = useState(null); // { paciente, nodo_origen, nodo_url }

  const buscarEnRedP2P = async () => {
    if (!busquedaDoc) return;
    setBuscando(true);
    setResultadoFederado(null);
    setMessage(null);

    // CORRECCIÓN CRÍTICA (feedback profesor):
    // Promise.allSettled en lugar de Promise.all
    // → Un nodo offline/lento NO colapsa la búsqueda en los otros nodos
    const promesas = SEDES.map(async (sede) => {
      try {
        const res = await fetch(
          `${sede.url}/recepcion/buscar/${busquedaDoc}`,
          { signal: AbortSignal.timeout(5000) }  // 5s timeout por nodo
        );
        if (!res.ok) return null;
        const data = await res.json();
        if (data.encontrado) return { ...data, nodo_url: sede.url, nodo_nombre: sede.nombre };
        return null;
      } catch {
        // Nodo inalcanzable → se ignora, no bloquea los demás
        return null;
      }
    });

    // Promise.allSettled: siempre resuelve aunque algunos fallen
    const settled = await Promise.allSettled(promesas);
    const encontrado = settled
      .filter(r => r.status === 'fulfilled' && r.value !== null)
      .map(r => r.value)
      .find(r => r !== null);  // Primer nodo que respondió con datos

    if (encontrado) {
      setResultadoFederado(encontrado);
    } else {
      setMessage({
        text: `Paciente con documento ${busquedaDoc} no encontrado en ningún nodo activo de la red P2P. Puede registrarlo como nuevo.`,
        type: 'error'
      });
      setSeccion1(prev => ({ ...prev, documento_id: busquedaDoc }));
    }
    setBuscando(false);
  };


  const importarDesdeFederado = async () => {
    if (!resultadoFederado) return;
    // Si el nodo origen es el nodo actual (sede activa), solo pre-llenar
    const esNodoActual = resultadoFederado.nodo_url === sedeVisualizacion.url;

    if (!esNodoActual) {
      // Llamar al endpoint de importar en el nodo ACTUAL
      try {
        const res = await fetch(`${sedeVisualizacion.url}/recepcion/importar`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ paciente: resultadoFederado.paciente, nodo_origen: resultadoFederado.nodo_origen })
        });
        const data = await res.json();
        setMessage({ text: data.message || data.error, type: res.ok ? 'success' : 'error' });
      } catch {
        setMessage({ text: 'Error al importar desde nodo remoto', type: 'error' });
      }
    }

    // Pre-llenar formulario con los datos del nodo de origen
    const p = resultadoFederado.paciente;
    setSeccion1({
      documento_id: String(p.documento_id),
      tipo_documento: p.tipo_documento || 'CC',
      pais_nacionalidad: p.pais_nacionalidad || 'CO',
      nombre_completo: p.nombre_completo || '',
      fecha_nacimiento: p.fecha_nacimiento || '',
      edad: p.edad || '',
      unidad_edad: p.unidad_edad || 'Años',
      sexo: p.sexo || 'M',
      genero: p.genero || 'Masculino',
      ocupacion: p.ocupacion || '',
      voluntad_anticipada: p.voluntad_anticipada || false,
      categoria_discapacidad: p.categoria_discapacidad || '',
      pais_residencia: p.pais_residencia || 'CO',
      municipio_residencia: p.municipio_residencia || '',
      etnia: p.etnia || ''
    });
    setResultadoFederado(null);
    setEtapaHC(1);
  };



  const postCitus = async (endpoint, payload) => {
    const res = await fetch(`${sedeVisualizacion.url}${endpoint}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    return { ok: res.ok, data };
  };

  const handleSeccion1 = async (e) => {
    e.preventDefault(); setLoading(true); setMessage(null);
    const { ok, data } = await postCitus('/recepcion/ingreso', { ...seccion1, documento_id: seccion1.documento_id }).catch(() => ({ ok: false, data: { error: 'Error de red' } }));
    setMessage(ok ? { text: data.message, type: 'success' } : { text: data.error, type: 'error' });
    if (ok) setEtapaHC(2);
    setLoading(false);
  };

  const handleSeccion2 = async (e) => {
    e.preventDefault(); setLoading(true); setMessage(null);
    const { ok, data } = await postCitus('/atencion/triaje', { ...seccion2, documento_id: seccion1.documento_id }).catch(() => ({ ok: false, data: { error: 'Error de red' } }));
    if (ok && data.atencion_id) setAtencionId(data.atencion_id);
    setMessage(ok ? { text: data.message, type: 'success' } : { text: data.error, type: 'error' });
    if (ok) setEtapaHC(3);
    setLoading(false);
  };

  const handleSeccion3 = async (e) => {
    e.preventDefault(); setLoading(true); setMessage(null);
    const { ok, data } = await postCitus('/atencion/medicamentos', { ...seccion3, documento_id: seccion1.documento_id, atencion_id: atencionId }).catch(() => ({ ok: false, data: { error: 'Error de red' } }));
    setMessage(ok ? { text: data.message, type: 'success' } : { text: data.error, type: 'error' });
    if (ok) setEtapaHC(4);
    setLoading(false);
  };

  const handleSeccion4 = async (e) => {
    e.preventDefault(); setLoading(true); setMessage(null);
    const { ok, data } = await postCitus('/atencion/diagnostico', { ...seccion4, documento_id: seccion1.documento_id, atencion_id: atencionId }).catch(() => ({ ok: false, data: { error: 'Error de red' } }));
    setMessage(ok ? { text: data.message, type: 'success' } : { text: data.error, type: 'error' });
    if (ok) setEtapaHC(5);
    setLoading(false);
  };

  const handleSeccion5 = async (e) => {
    e.preventDefault(); setLoading(true); setMessage(null);
    const { ok, data } = await postCitus('/egreso/salida', { ...seccion5, documento_id: seccion1.documento_id, atencion_id: atencionId, nombre_completo: seccion1.nombre_completo }).catch(() => ({ ok: false, data: { error: 'Error de red' } }));
    setMessage(ok ? { text: data.message, type: 'success' } : { text: data.error, type: 'error' });
    if (ok) { setEtapaHC(1); setSeccion1({ documento_id: '', tipo_documento: 'CC', pais_nacionalidad: 'CO', nombre_completo: '', fecha_nacimiento: '', edad: '', unidad_edad: 'Años', sexo: 'M', genero: 'Masculino', ocupacion: '', voluntad_anticipada: false, categoria_discapacidad: '', pais_residencia: 'CO', municipio_residencia: '', etnia: '' }); }
    setLoading(false);
  };

  const handleChange_paciente = (e) => setPaciente && null;





  // FUNCIÓN QUE TE FALTABA: gestionarNodo
  const gestionarNodo = (nombre) => {
    const apagadosCount = Object.values(nodosSimulados).filter(v => v === true).length;
    const encendidosCount = SEDES.length - apagadosCount;

    if (!nodosSimulados[nombre] && encendidosCount === 1) {
      const otro = SEDES.find(s => s.nombre !== nombre).nombre;
      setNodosSimulados(prev => ({ ...prev, [nombre]: true, [otro]: false }));
      alert(`⚠️ Regla de Disponibilidad: Activando ${otro} automáticamente.`);
    } else {
      setNodosSimulados(prev => ({ ...prev, [nombre]: !prev[nombre] }));
    }
  };
  // UBICACIÓN: Piso 4 (Manejadores)

  // 1. Lógica de Validación Estricta ($validate)
  const validarDocumentoFHIR = () => {
    if (paciente.numeroDocumento.length < 5) return "Número de documento inválido.";
    if (paciente.nombreCompleto.split(' ').length < 2) return "Ingrese nombre y apellido completo.";
    if (!paciente.eps) return "La EPS es obligatoria para el estándar nacional.";
    return null; // Todo OK
  };

  // 2. Exportación Masiva (Bulk Data Access)
  const exportarTodoElNodo = () => {
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(listaPacientes, null, 2));
    const link = document.createElement('a');
    link.setAttribute("href", dataStr);
    link.setAttribute("download", `BULK_DATA_${sedeVisualizacion.nombre}_${Date.now()}.json`);
    link.click();
  };
  // El Rate Limit lo controla el backend (Status 429)
  const handleSubmit = async (e) => {
    e.preventDefault();
    // APLICANDO $VALIDATE
    const error = validarDocumentoFHIR();
    if (error) {
      setMessage({ text: `⚠️ Error de Validación FHIR: ${error}`, type: "error" });
      return;
    }
    setLoading(true);

    const patientRes = {
      resourceType: "Patient",
      id: paciente.numeroDocumento,
      name: [{
        text: paciente.nombreCompleto,
        family: paciente.nombreCompleto.split(' ').slice(-1)[0],
        given: paciente.nombreCompleto.split(' ').slice(0, -1)
      }],
      gender: paciente.sexo === 'M' ? 'male' : 'female',
      birthDate: paciente.fechaNacimiento,
      meta: {
        profile: ["http://hl7.org/fhir/us/core/StructureDefinition/us-core-patient"]
      },
      extension: [
        { url: "http://uajs.edu.co/fhir/eps", valueString: paciente.eps },
        { url: "http://uajs.edu.co/fhir/rh", valueString: paciente.rh }
      ]
    };

    let exito = false;
    let rateLimited = false;

    for (const sede of SEDES) {
      if (nodosSimulados[sede.nombre]) continue;
      try {
        // ACTUALIZACIÓN FHIR: Endpoint estándar /fhir/Patient
        const res = await fetch(`${sede.url}/fhir/Patient`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/fhir+json' },
          body: JSON.stringify(patientRes)
        });
        if (res.status === 429) {
          rateLimited = true;
          break; // Detener flujo si hay bloqueo Anti-DoS
        }
        if (res.ok) { exito = true; break; }
      } catch (err) {
        console.error(`Error replicando en ${sede.nombre}:`, err);
      }
    }

    if (rateLimited) {
      setMessage({ text: "⚠️ BLOQUEO SEGURIDAD (ANTI-DOS): Demasiadas peticiones detectadas por el protocolo ISO27001.", type: "error" });
    } else {
      setMessage(exito ? { text: `✅ Paciente '${paciente.nombreCompleto}' Replicado en la Red P2P`, type: "success" } : { text: "❌ Error de conexión con la red", type: "error" });
    }
    setLoading(false);
  };
  // UBICACIÓN: Piso 4, debajo de handleSubmit
  const exportarDocumentoSoberano = (doc) => {
    if (!doc) return;

    // Limpiamos metadatos de CouchDB para que sea FHIR puro
    const { _id, _rev, ...fhirPuro } = doc;

    const blob = new Blob([JSON.stringify(fhirPuro, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `FHIR_Doc_${doc.id || 'export'}.json`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };
  // ==========================================
  // PISO 5: LA FACHADA (JSX / UI)
  // ==========================================
  return (
    <div className="App-container">
      <div className="colombia-stripe">
        <div className="stripe-yellow"></div>
        <div className="stripe-blue"></div>
        <div className="stripe-red"></div>
      </div>
      
      <header className="top-navbar">
        <div className="nav-brand">
          <span className="brand-icon">🏥</span>
          <div className="brand-text">
            <strong>RED SALUD</strong>
            <span>P2P Distribuida</span>
          </div>
        </div>
        <nav className="nav-links">
          <button className={paginaActual === 'recepcion' ? 'btn-nav active' : 'btn-nav'} onClick={() => {setPaginaActual('recepcion'); setMessage(null);}}>Recepción</button>
          <button className={paginaActual === 'registro' ? 'btn-nav active' : 'btn-nav'} onClick={() => {setPaginaActual('registro'); setMessage(null);}}>Historia Clínica</button>
          <button className={paginaActual === 'consulta_hc' ? 'btn-nav active' : 'btn-nav'} onClick={() => {setPaginaActual('consulta_hc'); setMessage(null);}}>Consulta HC</button>
          <button className={paginaActual === 'reportes' ? 'btn-nav active' : 'btn-nav'} onClick={() => {setPaginaActual('reportes'); setMessage(null);}}>Reportes</button>
          <button className={paginaActual === 'control' ? 'btn-nav active' : 'btn-nav'} onClick={() => {setPaginaActual('control'); setMessage(null);}}>Nodos P2P</button>
        </nav>
      </header>

      <main className="main-card">
        {paginaActual === 'recepcion' && (
          <div className="fade-in">
            <div className="header">
              <h1>RECEPCION</h1>
              <p><strong>{sedeVisualizacion.nombre}</strong></p>
            </div>

            {/* ── BÚSQUEDA FEDERADA P2P ── */}
            <div className="p2p-search-card">
              <div className="p2p-search-header">
                <span className="p2p-badge">🌐 RED P2P</span>
                <span>Buscar paciente en todos los nodos de la red</span>
              </div>
              <div className="p2p-search-row">
                <input
                  type="number"
                  className="p2p-search-input"
                  placeholder="Ingrese número de documento para buscar en toda la red..."
                  value={busquedaDoc}
                  onChange={e => setBusquedaDoc(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && buscarEnRedP2P()}
                />
                <button className="p2p-search-btn" onClick={buscarEnRedP2P} disabled={buscando || !busquedaDoc}>
                  {buscando ? '🔄 Consultando nodos...' : '🔍 Buscar en Red P2P'}
                </button>
              </div>
              <div className="p2p-nodes-hint">
                {SEDES.map((s, i) => (
                  <span key={i} className={`p2p-node-dot ${saludRed[s.nombre] === 'online' ? 'on' : 'off'}`}>
                    {saludRed[s.nombre] === 'online' ? '🟢' : '🔴'} {s.nombre}
                  </span>
                ))}
              </div>
            </div>

            {/* ── RESULTADO FEDERADO: card de importación ── */}
            {resultadoFederado && (
              <div className="federado-card fade-in">
                <div className="federado-header">
                  <span className="federado-icon">📡</span>
                  <div>
                    <h3>Paciente encontrado en la red P2P</h3>
                    <p>Registrado por primera vez en el nodo <strong className="nodo-highlight">{resultadoFederado.nodo_nombre || resultadoFederado.nodo_origen}</strong></p>
                  </div>
                </div>
                <div className="federado-datos">
                  <div><span>Nombre</span><strong>{resultadoFederado.paciente.nombre_completo}</strong></div>
                  <div><span>Documento</span><strong>{resultadoFederado.paciente.documento_id}</strong></div>
                  <div><span>Fecha Nac.</span><strong>{resultadoFederado.paciente.fecha_nacimiento}</strong></div>
                  <div><span>Municipio</span><strong>{resultadoFederado.paciente.municipio_residencia || '—'}</strong></div>
                  <div><span>Sexo</span><strong>{resultadoFederado.paciente.sexo}</strong></div>
                  <div><span>Tipo Doc.</span><strong>{resultadoFederado.paciente.tipo_documento}</strong></div>
                </div>
                <p className="federado-pregunta">
                  {resultadoFederado.nodo_url === sedeVisualizacion.url
                    ? '✅ Este paciente ya existe en este nodo. ¿Desea cargar sus datos al formulario para una nueva atención?'
                    : `¿Desea traer los datos de este paciente desde ${resultadoFederado.nodo_nombre || resultadoFederado.nodo_origen} hacia ${sedeVisualizacion.nombre}?`
                  }
                </p>
                <div className="federado-actions">
                  <button className="btn-federado-si" onClick={importarDesdeFederado}>
                    ✅ {resultadoFederado.nodo_url === sedeVisualizacion.url ? 'Cargar datos al formulario' : `Importar a ${sedeVisualizacion.nombre}`}
                  </button>
                  <button className="btn-federado-no" onClick={() => { setResultadoFederado(null); }}>
                    ✖ Cancelar / Registrar nuevo
                  </button>
                </div>
              </div>
            )}

            {/* Stepper */}
            <div className="stepper">
              {['1·Identificación','2·Triaje','3·Medicamentos','4·Diagnóstico','5·Egreso'].map((label,i) => (
                <div key={i} className={`step ${etapaHC === i+1 ? 'active' : etapaHC > i+1 ? 'done' : ''}`}>
                  <span className="step-num">{etapaHC > i+1 ? '✓' : i+1}</span>
                  <span className="step-label">{label}</span>
                </div>
              ))}
            </div>

            <div className="form-container">
              <div style={{marginBottom:'0.5rem'}}>
                <label>Sede activa: </label>
                <select onChange={(e) => setSedeVisualizacion(SEDES[parseInt(e.target.value)])}>
                  {SEDES.map((s,i) => <option key={i} value={i}>{s.nombre}</option>)}
                </select>
              </div>

              {message && <div className={`alert ${message.type}`}>{message.text}</div>}


              {/* ── SECCIÓN 1: IDENTIFICACIÓN (campos 1-15) ─────────────────── */}
              {etapaHC === 1 && (
                <form onSubmit={handleSeccion1} className="fhir-form">
                  <div className="form-section">
                    <h3><span className="num">01</span> Identificación del Usuario <small>(Campos 1–15 · MinSalud)</small></h3>
                    <div className="grid-3">
                      <div className="field">
                        <label>1. Tipo de Documento *</label>
                        <select name="tipo_documento" data-sec="s1" value={seccion1.tipo_documento} onChange={handleChange}>
                          {['CC','TI','CE','PA','RC','MS','AS'].map(t => <option key={t}>{t}</option>)}
                        </select>
                      </div>
                      <div className="field">
                        <label>2. Nº Documento *</label>
                        <input type="number" name="documento_id" data-sec="s1" value={seccion1.documento_id} onChange={handleChange} required />
                      </div>
                      <div className="field">
                        <label>3. País de Nacionalidad *</label>
                        <select name="pais_nacionalidad" data-sec="s1" value={seccion1.pais_nacionalidad} onChange={handleChange}>
                          {['CO','US','BR','AR','MX','CL','PE','ES'].map(c => <option key={c}>{c}</option>)}
                        </select>
                      </div>
                      <div className="field" style={{gridColumn:'span 2'}}>
                        <label>4. Nombre Completo *</label>
                        <input type="text" name="nombre_completo" data-sec="s1" value={seccion1.nombre_completo} onChange={handleChange} required />
                      </div>
                      <div className="field">
                        <label>5. Fecha de Nacimiento *</label>
                        <input type="date" name="fecha_nacimiento" data-sec="s1" value={seccion1.fecha_nacimiento} onChange={handleChange} required />
                      </div>
                      <div className="field">
                        <label>6. Edad *</label>
                        <input type="number" name="edad" data-sec="s1" value={seccion1.edad} onChange={handleChange} />
                      </div>
                      <div className="field">
                        <label>7. Unidad Edad *</label>
                        <select name="unidad_edad" data-sec="s1" value={seccion1.unidad_edad} onChange={handleChange}>
                          {['Años','Meses','Días'].map(u => <option key={u}>{u}</option>)}
                        </select>
                      </div>
                      <div className="field">
                        <label>8. Sexo *</label>
                        <select name="sexo" data-sec="s1" value={seccion1.sexo} onChange={handleChange}>
                          <option value="M">Masculino</option>
                          <option value="F">Femenino</option>
                          <option value="I">Indeterminado</option>
                        </select>
                      </div>
                      <div className="field">
                        <label>9. Género</label>
                        <select name="genero" data-sec="s1" value={seccion1.genero} onChange={handleChange}>
                          {['Masculino','Femenino','No Binario','Otro'].map(g => <option key={g}>{g}</option>)}
                        </select>
                      </div>
                      <div className="field">
                        <label>10. Ocupación</label>
                        <input type="text" name="ocupacion" data-sec="s1" value={seccion1.ocupacion} onChange={handleChange} />
                      </div>
                      <div className="field">
                        <label>11. Voluntad Anticipada</label>
                        <select name="voluntad_anticipada" data-sec="s1" value={seccion1.voluntad_anticipada} onChange={handleChange}>
                          <option value={false}>No</option><option value={true}>Sí</option>
                        </select>
                      </div>
                      <div className="field">
                        <label>12. Categoría Discapacidad</label>
                        <select name="categoria_discapacidad" data-sec="s1" value={seccion1.categoria_discapacidad} onChange={handleChange}>
                          {['','Ninguna','Física','Mental','Sensorial','Múltiple'].map(d => <option key={d}>{d}</option>)}
                        </select>
                      </div>
                      <div className="field">
                        <label>13. País de Residencia *</label>
                        <select name="pais_residencia" data-sec="s1" value={seccion1.pais_residencia} onChange={handleChange}>
                          {['CO','US','BR','AR','MX','CL','PE','ES'].map(c => <option key={c}>{c}</option>)}
                        </select>
                      </div>
                      <div className="field">
                        <label>14. Municipio de Residencia *</label>
                        <input type="text" name="municipio_residencia" data-sec="s1" value={seccion1.municipio_residencia} onChange={handleChange} placeholder="ej: Sincelejo" />
                      </div>
                      <div className="field">
                        <label>15. Etnia</label>
                        <select name="etnia" data-sec="s1" value={seccion1.etnia} onChange={handleChange}>
                          {['','Ninguna','Indígena','ROM','Raizal','Palenquero','Negro / Afro','Otro'].map(e => <option key={e}>{e}</option>)}
                        </select>
                      </div>
                    </div>
                  </div>
                  <button type="submit" className="btn-save-final" disabled={loading}>
                    {loading ? '⌛ Guardando en Citus...' : '➡ GUARDAR IDENTIFICACIÓN (1/5)'}
                  </button>
                </form>
              )}

              {/* ── SECCIÓN 2: TRIAJE (campos 16-24) ─────────────────────────── */}
              {etapaHC === 2 && (
                <form onSubmit={handleSeccion2} className="fhir-form">
                  <div className="form-section">
                    <h3><span className="num">02</span> Datos de la Atención / Triaje <small>(Campos 16–24)</small></h3>
                    <div className="grid-3">
                      <div className="field" style={{gridColumn:'span 2'}}>
                        <label>16. Entidad de Salud *</label>
                        <input type="text" name="entidad_salud" data-sec="s2" value={seccion2.entidad_salud} onChange={handleChange} required placeholder="EPS o IPS responsable" />
                      </div>
                      <div className="field">
                        <label>17. Fecha y Hora de Ingreso *</label>
                        <input type="datetime-local" name="fecha_ingreso" data-sec="s2" value={seccion2.fecha_ingreso} onChange={handleChange} required />
                      </div>
                      <div className="field">
                        <label>18. Modalidad de Entrega *</label>
                        <select name="modalidad_entrega" data-sec="s2" value={seccion2.modalidad_entrega} onChange={handleChange}>
                          {['Presencial','Telemedicina','Domiciliaria'].map(m => <option key={m}>{m}</option>)}
                        </select>
                      </div>
                      <div className="field">
                        <label>19. Entorno de Atención *</label>
                        <select name="entorno_atencion" data-sec="s2" value={seccion2.entorno_atencion} onChange={handleChange}>
                          {['Urgencias','Consulta','Hospitalización','Cirugía','Apoyo Diagnóstico'].map(e => <option key={e}>{e}</option>)}
                        </select>
                      </div>
                      <div className="field">
                        <label>20. Vía de Ingreso *</label>
                        <select name="via_ingreso" data-sec="s2" value={seccion2.via_ingreso} onChange={handleChange}>
                          {['Espontáneo','Referencia','Contrarreferencia'].map(v => <option key={v}>{v}</option>)}
                        </select>
                      </div>
                      <div className="field" style={{gridColumn:'span 3'}}>
                        <label>21. Causa de la Atención *</label>
                        <textarea name="causa_atencion" data-sec="s2" value={seccion2.causa_atencion} onChange={handleChange} rows="2" placeholder="Motivo de la consulta" />
                      </div>
                      <div className="field">
                        <label>22. Fecha y Hora Triage</label>
                        <input type="datetime-local" name="fecha_triage" data-sec="s2" value={seccion2.fecha_triage} onChange={handleChange} />
                      </div>
                      <div className="field">
                        <label>23. Clasificación Triage (Manchester)</label>
                        <select name="clasificacion_triage" data-sec="s2" value={seccion2.clasificacion_triage} onChange={handleChange}>
                          <option value="">-- No aplica --</option>
                          <option value="I">I – Resucitación</option>
                          <option value="II">II – Emergencia</option>
                          <option value="III">III – Urgente</option>
                          <option value="IV">IV – Menos urgente</option>
                          <option value="V">V – No urgente</option>
                        </select>
                      </div>
                      <div className="field">
                        <label>24. Comunidad Étnica</label>
                        <input type="text" name="comunidad_etnica" data-sec="s2" value={seccion2.comunidad_etnica} onChange={handleChange} placeholder="ej: Wayúu" />
                      </div>
                    </div>
                  </div>
                  <div style={{display:'flex',gap:'1rem'}}>
                    <button type="button" className="btn-bulk" onClick={() => setEtapaHC(1)}>← Volver</button>
                    <button type="submit" className="btn-save-final" disabled={loading} style={{flex:1}}>
                      {loading ? '⌛ Guardando en Citus...' : '➡ GUARDAR TRIAJE (2/5)'}
                    </button>
                  </div>
                </form>
              )}

              {/* ── SECCIÓN 3: MEDICAMENTOS (campos 25-35) ────────────────────── */}
              {etapaHC === 3 && (
                <form onSubmit={handleSeccion3} className="fhir-form">
                  <div className="form-section">
                    <h3><span className="num">03</span> Tecnologías en Salud / Medicamentos <small>(Campos 25–35)</small></h3>
                    <div className="grid-3">
                      <div className="field" style={{gridColumn:'span 2'}}>
                        <label>25. Medicamento / Tecnología *</label>
                        <input type="text" name="descripcion_medicamento" data-sec="s3" value={seccion3.descripcion_medicamento} onChange={handleChange} placeholder="ej: Acetaminofén 500mg" required />
                      </div>
                      <div className="field">
                        <label>26. Dosis</label>
                        <input type="text" name="dosis" data-sec="s3" value={seccion3.dosis} onChange={handleChange} placeholder="ej: 500mg" />
                      </div>
                      <div className="field">
                        <label>27. Vía de Administración</label>
                        <select name="via_administracion" data-sec="s3" value={seccion3.via_administracion} onChange={handleChange}>
                          {['Oral','Intravenosa','Intramuscular','Subcutánea','Tópica','Inhalatoria','Rectal'].map(v => <option key={v}>{v}</option>)}
                        </select>
                      </div>
                      <div className="field">
                        <label>28. Frecuencia</label>
                        <input type="text" name="frecuencia" data-sec="s3" value={seccion3.frecuencia} onChange={handleChange} placeholder="ej: Cada 8 horas" />
                      </div>
                      <div className="field">
                        <label>29. Días de Tratamiento *</label>
                        <input type="number" name="dias_tratamiento" data-sec="s3" value={seccion3.dias_tratamiento} onChange={handleChange} min="1" required />
                      </div>
                      <div className="field">
                        <label>30. Unidades Aplicadas *</label>
                        <input type="number" name="unidades_aplicadas" data-sec="s3" value={seccion3.unidades_aplicadas} onChange={handleChange} min="0" required />
                      </div>
                      <div className="field">
                        <label>31. Profesional de Salud *</label>
                        <select name="id_personal_salud" data-sec="s3" value={seccion3.id_personal_salud} onChange={handleChange} required>
                          <option value="">-- Seleccione profesional --</option>
                          {PROFESIONALES_SALUD.map(p => (
                            <option key={p.id} value={p.id}>{p.nombre} · {p.especialidad}</option>
                          ))}
                        </select>
                      </div>
                      <div className="field">
                        <label>32. Finalidad de la Tecnología</label>
                        <select name="finalidad_tecnologia" data-sec="s3" value={seccion3.finalidad_tecnologia} onChange={handleChange}>
                          {['Terapéutica','Diagnóstica','Paliativa','Preventiva','Rehabilitación'].map(f => <option key={f}>{f}</option>)}
                        </select>
                      </div>
                      <div className="field">
                        <label>33. Tipo Diagnóstico Ingreso</label>
                        <select name="tipo_diagnostico_ingreso" data-sec="s3" value={seccion3.tipo_diagnostico_ingreso} onChange={handleChange}>
                          {['Confirmado','Presuntivo','En estudio'].map(t => <option key={t}>{t}</option>)}
                        </select>
                      </div>
                      <div className="field">
                        <label>
                          34. Diagnóstico de Ingreso
                          <button type="button" style={{marginLeft:'0.5rem',fontSize:'0.7rem',padding:'2px 8px',borderRadius:'4px',border:'1px solid #6366f1',background:usarCIE11?'#6366f1':'transparent',color:usarCIE11?'#fff':'#6366f1',cursor:'pointer'}} onClick={() => setUsarCIE11(!usarCIE11)}>
                            {usarCIE11 ? '✦ CIE-11' : 'CIE-10'}
                          </button>
                        </label>
                        {usarCIE11 ? (
                          <select name="diagnostico_ingreso_cie11" data-sec="s3" value={seccion3.diagnostico_ingreso_cie11 || ''} onChange={handleChange}>
                            <option value="">-- Seleccione CIE-11 --</option>
                            {catalogoCIE11.map(c => <option key={c.codigo} value={c.codigo}>{c.codigo} – {c.titulo}</option>)}
                          </select>
                        ) : (
                          <select name="diagnostico_ingreso" data-sec="s3" value={seccion3.diagnostico_ingreso} onChange={handleChange}>
                            {CIE10.map(c => <option key={c.codigo} value={c.codigo}>{c.codigo} – {c.descripcion}</option>)}
                          </select>
                        )}
                      </div>
                      <div className="field">
                        <label>35. Tipo Diagnóstico Egreso</label>
                        <select name="tipo_diagnostico_egreso" data-sec="s3" value={seccion3.tipo_diagnostico_egreso} onChange={handleChange}>
                          {['Confirmado','Presuntivo','En estudio'].map(t => <option key={t}>{t}</option>)}
                        </select>
                      </div>
                    </div>
                  </div>
                  <div style={{display:'flex',gap:'1rem'}}>
                    <button type="button" className="btn-bulk" onClick={() => setEtapaHC(2)}>← Volver</button>
                    <button type="submit" className="btn-save-final" disabled={loading} style={{flex:1}}>
                      {loading ? '⌛ Guardando en Citus...' : '➡ GUARDAR MEDICAMENTOS (3/5)'}
                    </button>
                  </div>
                </form>
              )}

              {/* ── SECCIÓN 4: DIAGNÓSTICOS CIE-10 (campos 36-39) ────────────── */}
              {etapaHC === 4 && (
                <form onSubmit={handleSeccion4} className="fhir-form">
                  <div className="form-section">
                    <h3><span className="num">04</span> Diagnósticos CIE-10 <small>(Campos 36–39)</small></h3>
                    <div className="grid-2">
                      <div className="field">
                        <label>36. Diagnóstico de Egreso * (CIE-10)</label>
                        <select name="diagnostico_egreso" data-sec="s4" value={seccion4.diagnostico_egreso} onChange={handleChange} required>
                          {CIE10.map(c => <option key={c.codigo} value={c.codigo}>{c.codigo} – {c.descripcion}</option>)}
                        </select>
                      </div>
                      <div className="field">
                        <label>37. Diagnóstico Relacionado 1</label>
                        <select name="diagnostico_rel1" data-sec="s4" value={seccion4.diagnostico_rel1} onChange={handleChange}>
                          <option value="">-- Ninguno --</option>
                          {CIE10.map(c => <option key={c.codigo} value={c.codigo}>{c.codigo} – {c.descripcion}</option>)}
                        </select>
                      </div>
                      <div className="field">
                        <label>38. Diagnóstico Relacionado 2</label>
                        <select name="diagnostico_rel2" data-sec="s4" value={seccion4.diagnostico_rel2} onChange={handleChange}>
                          <option value="">-- Ninguno --</option>
                          {CIE10.map(c => <option key={c.codigo} value={c.codigo}>{c.codigo} – {c.descripcion}</option>)}
                        </select>
                      </div>
                      <div className="field">
                        <label>39. Diagnóstico Relacionado 3</label>
                        <select name="diagnostico_rel3" data-sec="s4" value={seccion4.diagnostico_rel3} onChange={handleChange}>
                          <option value="">-- Ninguno --</option>
                          {CIE10.map(c => <option key={c.codigo} value={c.codigo}>{c.codigo} – {c.descripcion}</option>)}
                        </select>
                      </div>
                    </div>
                  </div>
                  <div style={{display:'flex',gap:'1rem'}}>
                    <button type="button" className="btn-bulk" onClick={() => setEtapaHC(3)}>← Volver</button>
                    <button type="submit" className="btn-save-final" disabled={loading} style={{flex:1}}>
                      {loading ? '⌛ Guardando en Citus...' : '➡ GUARDAR DIAGNÓSTICOS (4/5)'}
                    </button>
                  </div>
                </form>
              )}

              {/* ── SECCIÓN 5: EGRESO (campos 40-57) ─────────────────────────── */}
              {etapaHC === 5 && (
                <form onSubmit={handleSeccion5} className="fhir-form">
                  <div className="form-section">
                    <h3><span className="num">05</span> Datos de Egreso <small>(Campos 40–57)</small></h3>
                    <div className="grid-3">
                      <div className="field">
                        <label>40. Fecha y Hora de Salida *</label>
                        <input type="datetime-local" name="fecha_salida" data-sec="s5" value={seccion5.fecha_salida} onChange={handleChange} required />
                      </div>
                      <div className="field">
                        <label>41. Condición de Salida *</label>
                        <select name="condicion_salida" data-sec="s5" value={seccion5.condicion_salida} onChange={handleChange}>
                          {['Vivo','Muerto'].map(c => <option key={c}>{c}</option>)}
                        </select>
                      </div>
                      <div className="field">
                        <label>42. Diagnóstico de Muerte (CIE-10)</label>
                        <input type="text" name="diagnostico_muerte" data-sec="s5" value={seccion5.diagnostico_muerte} onChange={handleChange} placeholder="Solo si aplica" />
                      </div>
                      <div className="field">
                        <label>43. Código del Prestador *</label>
                        <input type="text" name="codigo_prestador" data-sec="s5" value={seccion5.codigo_prestador} onChange={handleChange} required />
                      </div>
                      <div className="field">
                        <label>44. Tipo de Incapacidad</label>
                        <select name="tipo_incapacidad" data-sec="s5" value={seccion5.tipo_incapacidad} onChange={handleChange}>
                          <option value="">-- Ninguna --</option>
                          {['Temporal','Permanente Parcial','Permanente Total','Gran Invalidez','No aplica'].map(t => <option key={t}>{t}</option>)}
                        </select>
                      </div>
                      <div className="field">
                        <label>45. Días de Incapacidad</label>
                        <input type="number" name="dias_incapacidad" data-sec="s5" value={seccion5.dias_incapacidad} onChange={handleChange} />
                      </div>
                      <div className="field">
                        <label>46. Días Licencia Maternidad</label>
                        <input type="number" name="dias_lic_maternidad" data-sec="s5" value={seccion5.dias_lic_maternidad} onChange={handleChange} />
                      </div>
                      <div className="field" style={{gridColumn:'span 3'}}>
                        <label>47. Alergias</label>
                        <textarea name="alergias" data-sec="s5" value={seccion5.alergias} onChange={handleChange} rows="2" placeholder="ej: Penicilina, Mariscos" />
                      </div>
                      <div className="field" style={{gridColumn:'span 2'}}>
                        <label>48. Antecedentes Familiares</label>
                        <textarea name="antecedentes_familiares" data-sec="s5" value={seccion5.antecedentes_familiares} onChange={handleChange} rows="2" placeholder="ej: Padre: HTA, Madre: DM2" />
                      </div>
                      <div className="field">
                        <label>49. Riesgos Ocupacionales</label>
                        <textarea name="riesgos_ocupacionales" data-sec="s5" value={seccion5.riesgos_ocupacionales} onChange={handleChange} rows="2" placeholder="ej: Ruido, Polvo" />
                      </div>
                      <div className="field" style={{gridColumn:'span 2'}}>
                        <label>50. Responsable del Egreso *</label>
                        <input type="text" name="responsable_egreso" data-sec="s5" value={seccion5.responsable_egreso} onChange={handleChange} required placeholder="Nombre del médico" />
                      </div>
                      <div className="field">
                        <label>51. Zona de Residencia *</label>
                        <select name="zona_residencia" data-sec="s5" value={seccion5.zona_residencia} onChange={handleChange}>
                          {['Urbana','Rural','Centro Poblado'].map(z => <option key={z}>{z}</option>)}
                        </select>
                      </div>
                      <div className="field" style={{gridColumn:'span 2'}}>
                        <label>52. Dirección de Residencia *</label>
                        <input type="text" name="direccion_residencia" data-sec="s5" value={seccion5.direccion_residencia} onChange={handleChange} required />
                      </div>
                      <div className="field">
                        <label>53. Teléfono</label>
                        <input type="tel" name="telefono" data-sec="s5" value={seccion5.telefono} onChange={handleChange} />
                      </div>
                      <div className="field" style={{gridColumn:'span 2'}}>
                        <label>54. Correo Electrónico</label>
                        <input type="email" name="correo_electronico" data-sec="s5" value={seccion5.correo_electronico} onChange={handleChange} />
                      </div>
                      <div className="field">
                        <label>55. Nombre del Responsable</label>
                        <input type="text" name="nombre_responsable" data-sec="s5" value={seccion5.nombre_responsable} onChange={handleChange} />
                      </div>
                      <div className="field">
                        <label>56. Parentesco</label>
                        <select name="parentesco_responsable" data-sec="s5" value={seccion5.parentesco_responsable} onChange={handleChange}>
                          <option value="">-- Seleccione --</option>
                          {['Padre/Madre','Hijo/Hija','Esposo/Esposa','Hermano/Hermana','Abuelo/Abuela','Tío/Tía','Otro'].map(p => <option key={p}>{p}</option>)}
                        </select>
                      </div>
                      <div className="field">
                        <label>57. Teléfono del Responsable</label>
                        <input type="tel" name="telefono_responsable" data-sec="s5" value={seccion5.telefono_responsable} onChange={handleChange} />
                      </div>
                    </div>
                  </div>
                  <div style={{display:'flex',gap:'1rem'}}>
                    <button type="button" className="btn-bulk" onClick={() => setEtapaHC(4)}>← Volver</button>
                    <button type="submit" className="btn-save-final" disabled={loading} style={{flex:1,background:'linear-gradient(135deg,#16a34a,#15803d)'}}>
                      {loading ? '⌛ Archivando HC en Red P2P...' : '🏁 CERRAR HISTORIA CLÍNICA (5/5)'}
                    </button>
                  </div>
                </form>
              )}

            </div>
          </div>
        )}



        {paginaActual === 'registro' && (
          <div className="fade-in">
            {/* DASHBOARD SUPERIOR */}
            <div className="network-dashboard">
              {SEDES.map((s, i) => (
                <div key={i} className="node-status">
                  <span className={`status-dot ${saludRed[s.nombre] === 'online' ? 'online' : 'offline'}`}></span>
                  <span>{s.nombre}</span>
                </div>
              ))}
            </div>

            <div className="header">
              <h1>HISTORIAL PACIENTE NACIONAL</h1>
              <p><strong>{sedeVisualizacion.nombre}</strong></p>
            </div>

            <div className="form-container">
              {message && <div className={`alert ${message.type}`}>{message.text}</div>}

              <form onSubmit={handleSubmit} className="fhir-form">
                <div className="grid-layout">
                  {/* SECCIÓN 1 */}
                  <div className="form-section">
                    <h3><span className="num">01</span> Identificación y Perfil</h3>
                    <div className="grid-3">
                      <div className="field"><label>Documento *</label><input type="text" name="numeroDocumento" onChange={handleChange} required /></div>
                      <div className="field"><label>Nombre Completo *</label><input type="text" name="nombreCompleto" onChange={handleChange} required /></div>
                      <div className="field"><label>F. Nacimiento</label><input type="date" name="fechaNacimiento" onChange={handleChange} required /></div>
                      <div className="field"><label>Ocupación</label><input type="text" name="ocupacion" onChange={handleChange} /></div>
                      <div className="field"><label>Etnia</label><input type="text" name="etnia" onChange={handleChange} /></div>
                      <div className="field"><label>Sexo</label>
                        <select name="sexo" onChange={handleChange}><option value="M">Masculino</option><option value="F">Femenino</option></select>
                      </div>
                    </div>
                  </div>

                  {/* SECCIÓN 2 */}
                  <div className="form-section">
                    <h3><span className="num">02</span> Seguridad Social y Salud</h3>
                    <div className="grid-3">
                      <div className="field"><label>EPS</label><input type="text" name="eps" onChange={handleChange} /></div>
                      <div className="field"><label>Sisbén</label><input type="text" name="nivelSisben" onChange={handleChange} /></div>
                      <div className="field"><label>RH</label><input type="text" name="rh" onChange={handleChange} /></div>
                      <div className="field" style={{ gridColumn: "span 3" }}><label>Discapacidad / Antecedentes</label>
                        <textarea name="antecedentes" onChange={handleChange} rows="2"></textarea>
                      </div>
                    </div>
                  </div>
                </div>


                {/* BLOQUE 3: UBICACIÓN */}
                <div className="form-section mt-10">
                  <h3><span className="num">03</span> Ubicación y Contacto</h3>
                  <div className="grid-2">
                    <div className="field"><label>Dirección</label><input type="text" name="direccion" onChange={handleChange} /></div>
                    <div className="field"><label>Teléfono</label><input type="text" name="telefono" onChange={handleChange} /></div>
                  </div>
                </div>


              </form>
              {/* BLOQUE 04: EMERGENCIA Y ANTECEDENTES */}
              <div className="form-section mt-10">
                <h3><span className="num">04</span> Emergencia y Antecedentes</h3>
                <div className="grid-2">
                  <div className="field">
                    <label>Contacto de Emergencia</label>
                    <input type="text" name="responsable" onChange={handleChange} placeholder="Nombre del familiar" />
                  </div>
                  <div className="field">
                    <label>Parentesco</label>
                    <input type="text" name="parentesco" onChange={handleChange} />
                  </div>
                  <div className="field" style={{ gridColumn: "span 2" }}>
                    <label>Alergias Conocidas</label>
                    <textarea name="alergias" onChange={handleChange} rows="2" placeholder="Describa alergias o ponga 'Ninguna'"></textarea>
                  </div>
                </div>
              </div>

              {/* UBICACIÓN: Al final de todo el formulario, antes del botón de cierre */}

              <div className="rate-limit-container">


                {bloqueado && (
                  <div className="cooldown-alert">
                    <p>⚠️ Sistema bloqueado por seguridad (Anti-DoS)</p>
                    <div className="progress-bar-container">
                      <div className="progress-bar-fill"></div>
                    </div>
                  </div>
                )}
              </div>

              <button
                type="submit"
                className="btn-save-final"
                disabled={loading || bloqueado}
              >
                {loading ? '⌛ PROCESANDO...' : bloqueado ? '🚫 ACCESO RESTRINGIDO' : ' REGISTRAR PACIENTE'}
              </button>

              {/* TABLA DE INTEGRIDAD */}
              <div className="monitor-p2p">
                <div className="monitor-header">
                  <h3>📡 MONITOR DE REPLICACIÓN</h3>
                  <div className="actions-header">
                    <button onClick={exportarTodoElNodo} className="btn-bulk">📥 Exportar Nodo Completo </button>
                    <select onChange={(e) => setSedeVisualizacion(SEDES[e.target.value])}>
                      {SEDES.map((s, i) => <option key={i} value={i}>{s.nombre}</option>)}
                    </select>
                  </div>
                </div>
                <table>
                  <thead><tr><th>Paciente</th><th>Estado</th><th>Hash de Firma</th><th>Estándar</th><th>Interoperabilidad</th></tr></thead>
                  <tbody>
                    {listaPacientes.map((p, i) => {
                      const esFHIR = p.resourceType === "Patient";
                      let adulterado = false;
                      let nombre = "Desconocido";
                      let firma = "N/A";

                      if (esFHIR) {
                        nombre = p.name?.[0]?.text || "Sin Nombre";
                        const hashActual = generarSelloIntegridad(p);
                        firma = p.p2p_audit?.hash_firma || "N/A";
                        adulterado = firma !== "N/A" && hashActual !== firma;
                      } else {
                        nombre = p.nombreCompleto || "Legacy";
                      }

                      return (
                        <tr key={i} className={adulterado ? "row-adulterada" : ""}>
                          <td>{nombre}</td>
                          <td>
                            <span className={adulterado ? "badge-danger" : "badge-success"}>
                              {adulterado ? "⚠️ ADULTERADO" : "✅ ÍNTEGRO"}
                            </span>
                          </td>
                          <td><code>{firma}</code></td>
                          <td><span className="status-sync">{esFHIR ? "📜 FHIR" : "📄 Legacy"}</span></td>
                          <td>
                            <button
                              className="btn-export"
                              onClick={() => exportarDocumentoSoberano(p)}
                              title="Exportar a Estándar FHIR R4"
                            >
                              📥 Descargar JSON
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {paginaActual === 'control' && (
          /* PANEL DE CONTROL DE NODOS */
          <div className="nodos-container fade-in">
            <div className="admin-header">
              <h2>CENTRO DE CONTROL SOBERANO</h2>
            </div>
            <div className="nodos-grid-admin">
              {SEDES.map((s, i) => (
                <div className={`nodo-card-admin ${saludRed[s.nombre] === 'online' ? 'online' : 'offline'}`}>
                  <div className="nodo-indicator">
                    {/* Cambiamos el emoji por uno verde cuando esté online */}
                    {saludRed[s.nombre] === 'online' ? '🟢' : '🔴'}
                  </div>
                  <h3>{s.nombre}</h3>
                  <button
                    className={`btn-action ${nodosSimulados[s.nombre] ? 'on' : 'off'}`}
                    onClick={() => gestionarNodo(s.nombre)}
                  >
                    {nodosSimulados[s.nombre] ? 'Levantar Nodo' : 'Apagar Nodo'}
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ═══════════════════════════════════════════════ */}
        {/* PÁGINA: CONSULTA HC CONSOLIDADA (Requisito 4.4) */}
        {/* ═══════════════════════════════════════════════ */}
        {paginaActual === 'consulta_hc' && (
          <ConsultaHC sedeVisualizacion={sedeVisualizacion} SEDES={SEDES} />
        )}

        {/* ═══════════════════════════════════════════════ */}
        {/* PÁGINA: REPORTES / DASHBOARD (Requisito 4.5)   */}
        {/* ═══════════════════════════════════════════════ */}
        {paginaActual === 'reportes' && (
          <DashboardReportes sedeVisualizacion={sedeVisualizacion} SEDES={SEDES} saludRed={saludRed} />
        )}
      </main>
    </div>
  );
}

// ==========================================
// COMPONENTE: CONSULTA HC CONSOLIDADA (Requisito 4.4)
// ==========================================
function ConsultaHC({ sedeVisualizacion, SEDES }) {
  const [docBuscar, setDocBuscar] = React.useState('');
  const [hc, setHc] = React.useState(null);
  const [buscandoHC, setBuscandoHC] = React.useState(false);
  const [errorHC, setErrorHC] = React.useState(null);
  const [nodoOrigen, setNodoOrigen] = React.useState('');

  const buscarHC = async () => {
    if (!docBuscar) return;
    setBuscandoHC(true); setHc(null); setErrorHC(null);
    // Buscar en todos los nodos
    for (const sede of SEDES) {
      try {
        const res = await fetch(`${sede.url}/hc/completa/${docBuscar}`, { signal: AbortSignal.timeout(8000) });
        if (res.ok) {
          const data = await res.json();
          setHc(data); setNodoOrigen(data.nodo || sede.nombre);
          setBuscandoHC(false);
          return;
        }
      } catch { /* nodo inalcanzable */ }
    }
    setErrorHC('Paciente no encontrado en ningún nodo de la red P2P.');
    setBuscandoHC(false);
  };

  const imprimirHC = () => { window.print(); };

  return (
    <div className="fade-in">
      <div className="header">
        <h1>CONSULTAR PACIENTE</h1>
      </div>
      <div className="p2p-search-card">
        <div className="p2p-search-row">
          <input type="number" className="p2p-search-input" placeholder="Documento del paciente..."
            value={docBuscar} onChange={e => setDocBuscar(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && buscarHC()} />
          <button className="p2p-search-btn" onClick={buscarHC} disabled={buscandoHC || !docBuscar}>
            {buscandoHC ? '🔄 Consultando...' : '🔍 Buscar HC Completa'}
          </button>
          {hc && <button className="btn-bulk" onClick={imprimirHC}>🖨️ Imprimir / PDF</button>}
        </div>
      </div>

      {errorHC && <div className="alert error">{errorHC}</div>}

      {hc && (
        <div className="hc-consolidada" id="hc-print-area">
          <div className="hc-header-badge">
            <span>📡 Datos desde nodo: <strong>{nodoOrigen}</strong></span>
          </div>

          {/* Paciente */}
          <div className="form-section">
            <h3><span className="num">01</span> Identificación del Paciente</h3>
            <div className="grid-3">
              {hc.paciente && Object.entries(hc.paciente).filter(([k]) => !['hash_integridad','created_at','updated_at'].includes(k)).map(([k,v]) => (
                <div className="field" key={k}><label>{k.replace(/_/g,' ')}</label><div style={{padding:'6px 0',fontWeight:600}}>{String(v ?? '—')}</div></div>
              ))}
            </div>
          </div>

          {/* Atenciones */}
          {hc.atenciones?.length > 0 && (
            <div className="form-section">
              <h3><span className="num">02</span> Atenciones ({hc.atenciones.length})</h3>
              <table><thead><tr><th>Fecha</th><th>Entidad</th><th>Entorno</th><th>Triage</th><th>Causa</th></tr></thead>
                <tbody>{hc.atenciones.map((a,i) => (
                  <tr key={i}><td>{a.fecha_ingreso}</td><td>{a.entidad_salud}</td><td>{a.entorno_atencion}</td><td>{a.clasificacion_triage || '—'}</td><td>{a.causa_atencion}</td></tr>
                ))}</tbody></table>
            </div>
          )}

          {/* Medicamentos */}
          {hc.medicamentos?.length > 0 && (
            <div className="form-section">
              <h3><span className="num">03</span> Medicamentos ({hc.medicamentos.length})</h3>
              <table><thead><tr><th>Medicamento</th><th>Dosis</th><th>Vía</th><th>Frecuencia</th><th>Días</th></tr></thead>
                <tbody>{hc.medicamentos.map((m,i) => (
                  <tr key={i}><td>{m.descripcion_medicamento}</td><td>{m.dosis}</td><td>{m.via_administracion}</td><td>{m.frecuencia}</td><td>{m.dias_tratamiento}</td></tr>
                ))}</tbody></table>
            </div>
          )}

          {/* Diagnósticos */}
          {hc.diagnosticos?.length > 0 && (
            <div className="form-section">
              <h3><span className="num">04</span> Diagnósticos ({hc.diagnosticos.length})</h3>
              <table><thead><tr><th>Dx Principal</th><th>Relacionado 1</th><th>Relacionado 2</th><th>Relacionado 3</th></tr></thead>
                <tbody>{hc.diagnosticos.map((d,i) => (
                  <tr key={i}><td><strong>{d.diagnostico_egreso}</strong></td><td>{d.diagnostico_rel1 || '—'}</td><td>{d.diagnostico_rel2 || '—'}</td><td>{d.diagnostico_rel3 || '—'}</td></tr>
                ))}</tbody></table>
            </div>
          )}

          {/* Egresos */}
          {hc.egresos?.length > 0 && (
            <div className="form-section">
              <h3><span className="num">05</span> Egresos ({hc.egresos.length})</h3>
              <table><thead><tr><th>Fecha</th><th>Condición</th><th>Responsable</th><th>Dirección</th><th>Teléfono</th></tr></thead>
                <tbody>{hc.egresos.map((e,i) => (
                  <tr key={i}><td>{e.fecha_salida}</td><td>{e.condicion_salida}</td><td>{e.responsable_egreso}</td><td>{e.direccion_residencia}</td><td>{e.telefono || '—'}</td></tr>
                ))}</tbody></table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ==========================================
// COMPONENTE: DASHBOARD DE REPORTES (Requisito 4.5)
// ==========================================
function DashboardReportes({ sedeVisualizacion, SEDES, saludRed }) {
  const [metricas, setMetricas] = React.useState(null);
  const [cargando, setCargando] = React.useState(true);
  const [healthNodes, setHealthNodes] = React.useState({});

  React.useEffect(() => {
    const cargar = async () => {
      setCargando(true);
      try {
        const res = await fetch(`${sedeVisualizacion.url}/reportes/metricas`);
        if (res.ok) setMetricas(await res.json());
      } catch { setMetricas(null); }
      // Health de cada nodo
      const h = {};
      for (const s of SEDES) {
        try {
          const r = await fetch(`${s.url}/health/full`, { signal: AbortSignal.timeout(5000) });
          if (r.headers.get('content-type')?.includes('application/json')) {
            h[s.nombre] = await r.json();
          } else {
            h[s.nombre] = r.ok ? await r.json() : { couchdb: 'unknown', citus: 'unknown', hapi_fhir: 'unknown' };
          }
        } catch { h[s.nombre] = { couchdb: 'offline', citus: 'offline', hapi_fhir: 'offline' }; }
      }
      setHealthNodes(h);
      setCargando(false);
    };
    cargar();
    const iv = setInterval(cargar, 15000);
    return () => clearInterval(iv);
  }, [sedeVisualizacion]);

  const SimpleBar = ({ data, labelKey, valueKey, color }) => {
    if (!data || data.length === 0) return <p style={{opacity:.5}}>Sin datos</p>;
    const max = Math.max(...data.map(d => d[valueKey]));
    return (
      <div style={{display:'flex',flexDirection:'column',gap:'6px'}}>
        {data.map((d,i) => (
          <div key={i} style={{display:'flex',alignItems:'center',gap:'8px'}}>
            <span style={{minWidth:'140px',fontSize:'0.8rem',textAlign:'right'}}>{d[labelKey]}</span>
            <div style={{flex:1,background:'#1e293b',borderRadius:'4px',overflow:'hidden',height:'22px'}}>
              <div style={{width:`${(d[valueKey]/max)*100}%`,background:color||'#6366f1',height:'100%',borderRadius:'4px',transition:'width 0.5s'}}></div>
            </div>
            <span style={{minWidth:'30px',fontWeight:700,fontSize:'0.85rem'}}>{d[valueKey]}</span>
          </div>
        ))}
      </div>
    );
  };

  return (
    <div className="fade-in">
      <div className="header">
        <h1>TABLA DE REGISTROS HISTORICO</h1>
        <p><strong>{sedeVisualizacion.nombre}</strong></p>
      </div>

      {cargando && <div className="alert success">⏳ Cargando métricas...</div>}

      {/* HEALTH DE NODOS */}
      <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(220px,1fr))',gap:'1rem',marginBottom:'1.5rem'}}>
        {SEDES.map((s,i) => {
          const h = healthNodes[s.nombre] || {};
          const estado = saludRed?.[s.nombre] === 'online' ? '🟢' : '🔴';
          return (
            <div key={i} className="form-section" style={{textAlign:'center',padding:'1rem'}}>
              <h3 style={{margin:'0 0 8px'}}>{estado} {s.nombre}</h3>
              <div style={{fontSize:'0.8rem',display:'flex',flexDirection:'column',gap:'4px'}}>
                <span>CouchDB: <strong style={{color:h.couchdb==='online'?'#22c55e':'#ef4444'}}>{h.couchdb || '?'}</strong></span>
                <span>Citus: <strong style={{color:h.citus==='online'?'#22c55e':'#ef4444'}}>{h.citus || '?'}</strong></span>
                <span>HAPI FHIR: <strong style={{color:h.hapi_fhir==='online'?'#22c55e':'#ef4444'}}>{h.hapi_fhir || '?'}</strong></span>
              </div>
            </div>
          );
        })}
      </div>

      {metricas && (
        <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(300px,1fr))',gap:'1.5rem'}}>
          {/* Tarjeta: Total Pacientes */}
          <div className="form-section" style={{textAlign:'center'}}>
            <h3 style={{margin:'0'}}>🏥 Total Pacientes</h3>
            <div style={{fontSize:'3rem',fontWeight:800,color:'#6366f1',margin:'0.5rem 0'}}>{metricas.total_pacientes}</div>
          </div>

          {/* Tarjeta: Por Sexo */}
          <div className="form-section">
            <h3><span className="num">👤</span> Pacientes por Sexo</h3>
            <SimpleBar data={metricas.pacientes_por_sexo} labelKey="sexo" valueKey="cantidad" color="#8b5cf6" />
          </div>

          {/* Tarjeta: Top Diagnósticos */}
          <div className="form-section" style={{gridColumn:'span 2'}}>
            <h3><span className="num">🩺</span> Top Diagnósticos CIE-10</h3>
            <SimpleBar data={metricas.top_diagnosticos} labelKey="descripcion" valueKey="total" color="#f59e0b" />
          </div>

          {/* Tarjeta: Triage */}
          <div className="form-section">
            <h3><span className="num">🚨</span> Atenciones por Triage</h3>
            <SimpleBar data={metricas.atenciones_por_triage} labelKey="nivel" valueKey="cantidad" color="#ef4444" />
          </div>

          {/* Tarjeta: Entorno */}
          <div className="form-section">
            <h3><span className="num">🏢</span> Atenciones por Entorno</h3>
            <SimpleBar data={metricas.atenciones_por_entorno} labelKey="entorno" valueKey="cantidad" color="#22c55e" />
          </div>

          {/* Tarjeta: Egresos */}
          <div className="form-section">
            <h3><span className="num">🚪</span> Egresos por Condición</h3>
            <SimpleBar data={metricas.egresos_por_condicion} labelKey="condicion" valueKey="cantidad" color="#06b6d4" />
          </div>

          {/* Tarjeta: Últimos 7 días */}
          <div className="form-section">
            <h3><span className="num">📅</span> Atenciones Últimos 7 Días</h3>
            <SimpleBar data={metricas.atenciones_ultimos_7_dias} labelKey="dia" valueKey="cantidad" color="#a855f7" />
          </div>
        </div>
      )}

      {/* Enlace a Grafana */}
      <div className="form-section" style={{textAlign:'center',marginTop:'1.5rem'}}>
        <h3>🔗 Observabilidad Avanzada</h3>
        <p>Prometheus + Grafana con paneles de uptime, latencia y errores de los 3 nodos.</p>
        <a href="http://localhost:3001" target="_blank" rel="noopener noreferrer" className="btn-save-final" style={{display:'inline-block',textDecoration:'none',maxWidth:'300px'}}>
          Abrir Grafana Dashboard →
        </a>
        <a href="http://localhost:9090" target="_blank" rel="noopener noreferrer" className="btn-bulk" style={{display:'inline-block',textDecoration:'none',maxWidth:'300px',marginLeft:'1rem'}}>
          Abrir Prometheus →
        </a>
      </div>
    </div>
  );
}

export default App;