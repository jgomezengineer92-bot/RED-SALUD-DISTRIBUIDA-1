import React, { useState, useEffect } from 'react';
import './Nodos.css';

const SEDES_DATA = [
  { nombre: 'La Guajira', id: 0 },
  { nombre: 'Amazonas', id: 1 },
  { nombre: 'Guainía', id: 2 },
  { nombre: 'Nariño', id: 3 }
];

const Nodos = ({ volver }) => {
  const [estados, setEstados] = useState({
    'La Guajira': true, 'Amazonas': true, 'Guainía': true, 'Nariño': true
  });
  const [mensaje, setMensaje] = useState("");

  const toggleNodo = (nombre) => {
    const nodosActivos = Object.values(estados).filter(v => v === true).length;
    
    if (estados[nombre] && nodosActivos === 1) {
      // LOGICA: Si intenta apagar el último, encendemos otro automáticamente
      const otroNodo = SEDES_DATA.find(s => s.nombre !== nombre).nombre;
      setEstados(prev => ({ ...prev, [nombre]: false, [otroNodo]: true }));
      setMensaje(`⚠️ Sistema P2P Protegido: Se activó ${otroNodo} para evitar caída total.`);
      setTimeout(() => setMensaje(""), 4000);
    } else {
      setEstados(prev => ({ ...prev, [nombre]: !prev[nombre] }));
    }
  };

  const reiniciar = (nombre) => {
    setEstados(prev => ({ ...prev, [nombre]: false }));
    setMensaje(`🔄 Reiniciando nodo ${nombre}...`);
    setTimeout(() => {
      setEstados(prev => ({ ...prev, [nombre]: true }));
      setMensaje("");
    }, 2000);
  };

  return (
    <div className="nodos-page">
      <button onClick={volver} className="btn-nav">⬅️ Volver al Registro</button>
      <header>
        <h1>Centro de Control de Infraestructura</h1>
        <p>Pruebas de Resiliencia y Tolerancia a Fallos</p>
      </header>

      {mensaje && <div className="alerta-seguridad">{mensaje}</div>}

      <div className="nodos-grid">
        {SEDES_DATA.map(s => (
          <div key={s.id} className={`nodo-card ${estados[s.nombre] ? 'online' : 'offline'}`}>
            <div className="nodo-icon">{estados[s.nombre] ? '🌐' : '💀'}</div>
            <h3>{s.nombre}</h3>
            <p>Estado: <strong>{estados[s.nombre] ? 'ACTIVO' : 'INACTIVO'}</strong></p>
            
            <div className="btn-group">
              <button 
                className={`btn-node ${estados[s.nombre] ? 'btn-off' : 'btn-on'}`}
                onClick={() => toggleNodo(s.nombre)}
              >
                {estados[s.nombre] ? 'Apagar Nodo' : 'Encender Nodo'}
              </button>
              <button className="btn-node btn-reset" onClick={() => reiniciar(s.nombre)}>Reiniciar</button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default Nodos;