import React, { useMemo, useRef, useState } from 'react';
import {
  Activity, AlertTriangle, MapPin, Plane,
  Ship, TrainFront, Truck, ZoomIn, ZoomOut, LocateFixed
} from 'lucide-react';

const MODE_META = {
  road: { label: 'ROAD', color: '#94a3b8', Icon: Truck },
  rail: { label: 'RAIL', color: '#a78bfa', Icon: TrainFront },
  air: { label: 'AIR', color: '#60a5fa', Icon: Plane },
  sea: { label: 'SEA', color: '#22d3ee', Icon: Ship },
  transfer: { label: 'TRANSFER', color: '#64748b', Icon: Activity },
};

const TYPE_META = {
  port: { label: 'PORT', color: '#22d3ee', shape: 'square' },
  airport: { label: 'AIRPORT', color: '#60a5fa', shape: 'diamond' },
  rail_hub: { label: 'RAIL HUB', color: '#a78bfa', shape: 'circle' },
  rail_terminal: { label: 'RAIL TERMINAL', color: '#a78bfa', shape: 'circle' },
  distribution_hub: { label: 'ROAD HUB', color: '#94a3b8', shape: 'circle' },
  choke_point: { label: 'CHOKE POINT', color: '#f59e0b', shape: 'triangle' },
};

const WORLD = 256;

function project(lon, lat) {
  const clampedLat = Math.max(-85.0511, Math.min(85.0511, Number(lat)));
  const x = ((Number(lon) + 180) / 360) * WORLD;
  const sin = Math.sin((clampedLat * Math.PI) / 180);
  const y = (0.5 - Math.log((1 + sin) / (1 - sin)) / (4 * Math.PI)) * WORLD;
  return [x, y];
}

function routeSignature(rec) {
  return (rec?.legs || []).map((leg) => `${leg.from}->${leg.to}:${String(leg.mode).toLowerCase()}`).join('|');
}

function riskColor(value = 0) {
  if (value >= 0.75) return '#ef4444';
  if (value >= 0.45) return '#f59e0b';
  return '#10b981';
}

function TileLayer({ zoom }) {
  const z = Math.max(1, Math.min(3, Math.round(zoom)));
  const n = 2 ** z;
  const tiles = [];
  for (let x = 0; x < n; x += 1) {
    for (let y = 0; y < n; y += 1) {
      tiles.push(
        <image
          key={`${z}-${x}-${y}`}
          href={`https://tile.openstreetmap.org/${z}/${x}/${y}.png`}
          x={(x / n) * WORLD}
          y={(y / n) * WORLD}
          width={WORLD / n + 0.05}
          height={WORLD / n + 0.05}
          preserveAspectRatio="none"
          opacity="0.34"
        />
      );
    }
  }
  return <g className="network-map-tiles">{tiles}</g>;
}

function NodeGlyph({ node, selected, blocked, onClick }) {
  const meta = TYPE_META[node.type] || TYPE_META.distribution_hub;
  const [x, y] = project(node.lon, node.lat);
  const color = blocked ? '#ef4444' : meta.color;
  const size = selected ? 5.2 : node.importance >= 9 ? 4.2 : 3.2;

  return (
    <g
      className={`network-node ${selected ? 'is-selected' : ''} ${blocked ? 'is-blocked' : ''}`}
      transform={`translate(${x} ${y})`}
      onClick={(event) => { event.stopPropagation(); onClick(node); }}
      role="button"
      tabIndex={0}
      onKeyDown={(event) => event.key === 'Enter' && onClick(node)}
    >
      {selected && <circle r="8" fill="none" stroke="#f8fafc" strokeOpacity="0.8" strokeWidth="0.8" />}
      {blocked && <circle r="7" fill="rgba(239,68,68,0.18)" stroke="#ef4444" strokeWidth="1.1" />}
      {meta.shape === 'square' && <rect x={-size} y={-size} width={size * 2} height={size * 2} rx="1" fill={color} stroke="#020617" strokeWidth="1" />}
      {meta.shape === 'diamond' && <rect x={-size} y={-size} width={size * 2} height={size * 2} rx="1" fill={color} stroke="#020617" strokeWidth="1" transform="rotate(45)" />}
      {meta.shape === 'triangle' && <path d={`M 0 ${-size - 1} L ${size + 1} ${size} L ${-size - 1} ${size} Z`} fill={color} stroke="#020617" strokeWidth="1" />}
      {meta.shape === 'circle' && <circle r={size} fill={color} stroke="#020617" strokeWidth="1" />}
      {blocked && <line x1="-5" y1="-5" x2="5" y2="5" stroke="#fff" strokeWidth="1.2" />}
    </g>
  );
}

export default function NetworkMap({
  network,
  recommendations,
  selectedRouteIndex = 0,
  onRouteSelect,
  activeScenario,
  loading = false,
}) {
  const svgRef = useRef(null);
  const [view, setView] = useState({ x: 0, y: 0, zoom: 1 });
  const [drag, setDrag] = useState(null);
  const [selectedNode, setSelectedNode] = useState(null);

  const nodes = network?.nodes || [];
  const edges = network?.edges || [];
  const selectedRoute = recommendations?.[selectedRouteIndex] || null;
  const blockedIds = useMemo(
    () => new Set(activeScenario?.affected_nodes || []),
    [activeScenario]
  );

  const nodeById = useMemo(() => new Map(nodes.map((n) => [n.id, n])), [nodes]);

  const routeEdgeKeys = useMemo(() => {
    const keys = new Set();
    (selectedRoute?.legs || []).forEach((leg) => {
      if (leg.from && leg.to && leg.from !== leg.to) {
        keys.add(`${leg.from}|${leg.to}|${String(leg.mode || '').toLowerCase()}`);
      }
    });
    return keys;
  }, [selectedRoute]);

  const routeNodes = useMemo(() => {
    const ids = new Set();
    (selectedRoute?.legs || []).forEach((leg) => {
      if (leg.from) ids.add(leg.from);
      if (leg.to) ids.add(leg.to);
    });
    return ids;
  }, [selectedRoute]);

  const visibleEdges = useMemo(() => {
    return edges.filter((edge) => nodeById.has(edge.source) && nodeById.has(edge.target));
  }, [edges, nodeById]);

  const transform = `translate(${view.x} ${view.y}) translate(${WORLD / 2} ${WORLD / 2}) scale(${view.zoom}) translate(${-WORLD / 2} ${-WORLD / 2})`;

  const handlePointerDown = (event) => {
    if (event.button !== 0) return;
    event.currentTarget.setPointerCapture?.(event.pointerId);
    setDrag({ x: event.clientX, y: event.clientY, startX: view.x, startY: view.y });
  };

  const handlePointerMove = (event) => {
    if (!drag) return;
    const rect = svgRef.current?.getBoundingClientRect();
    if (!rect) return;
    const scale = WORLD / rect.width;
    setView((current) => ({
      ...current,
      x: drag.startX + (event.clientX - drag.x) * scale,
      y: drag.startY + (event.clientY - drag.y) * scale,
    }));
  };

  const handlePointerUp = () => setDrag(null);

  const zoomBy = (delta) => {
    setView((current) => ({ ...current, zoom: Math.max(0.75, Math.min(5, current.zoom + delta)) }));
  };

  const resetView = () => setView({ x: 0, y: 0, zoom: 1 });

  return (
    <section className="network-map-card">
      <div className="network-map-header">
        <div>
          <div className="network-map-title"><MapPin size={15} /> Multimodal Network</div>
          <div className="network-map-subtitle">
            Live topology from <code>/api/network</code> · {nodes.length} nodes · {edges.length} corridors
          </div>
        </div>
        <div className="network-map-tools">
          <button onClick={() => zoomBy(0.35)} title="Zoom in"><ZoomIn size={15} /></button>
          <button onClick={() => zoomBy(-0.35)} title="Zoom out"><ZoomOut size={15} /></button>
          <button onClick={resetView} title="Reset map"><LocateFixed size={15} /></button>
        </div>
      </div>

      <div
        className="network-map-canvas"
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerCancel={handlePointerUp}
        onWheel={(event) => { event.preventDefault(); zoomBy(event.deltaY < 0 ? 0.22 : -0.22); }}
      >
        <svg ref={svgRef} viewBox="0 0 256 256" preserveAspectRatio="xMidYMid meet">
          <rect width="256" height="256" fill="#07101d" />
          <g opacity="0.2" stroke="#64748b" strokeWidth="0.18">
            {[-60, -30, 0, 30, 60].map((lat) => {
              const [, y] = project(0, lat);
              return <line key={`lat-${lat}`} x1="0" x2="256" y1={y} y2={y} />;
            })}
            {[-120, -60, 0, 60, 120].map((lon) => {
              const [x] = project(lon, 0);
              return <line key={`lon-${lon}`} x1={x} x2={x} y1="0" y2="256" />;
            })}
          </g>

          <g transform={transform}>
            <TileLayer zoom={view.zoom} />

            {visibleEdges.map((edge, index) => {
              const source = nodeById.get(edge.source);
              const target = nodeById.get(edge.target);
              const [x1, y1] = project(source.lon, source.lat);
              const [x2, y2] = project(target.lon, target.lat);
              const mode = String(edge.mode || '').toLowerCase();
              const meta = MODE_META[mode] || MODE_META.transfer;
              const key = `${edge.source}|${edge.target}|${mode}`;
              const selected = routeEdgeKeys.has(key)
                || routeEdgeKeys.has(`${edge.target}|${edge.source}|${mode}`);
              const blocked = blockedIds.has(edge.source) || blockedIds.has(edge.target);
              return (
                <line
                  key={`${edge.source}-${edge.target}-${mode}-${index}`}
                  x1={x1} y1={y1} x2={x2} y2={y2}
                  stroke={selected ? riskColor(selectedRoute?.threat_level || 0.2) : blocked ? '#ef4444' : meta.color}
                  strokeWidth={selected ? 1.8 : blocked ? 0.7 : 0.28}
                  strokeOpacity={selected ? 1 : blocked ? 0.38 : 0.22}
                  strokeDasharray={selected && mode === 'sea' ? '2 1' : undefined}
                />
              );
            })}

            {(selectedRoute?.legs || []).map((leg, index) => {
              if (!leg.from || !leg.to || leg.from === leg.to) return null;
              const a = nodeById.get(leg.from);
              const b = nodeById.get(leg.to);
              if (!a || !b) return null;
              const [x1, y1] = project(a.lon, a.lat);
              const [x2, y2] = project(b.lon, b.lat);
              const meta = MODE_META[String(leg.mode || '').toLowerCase()] || MODE_META.transfer;
              return (
                <line
                  key={`route-leg-${index}`}
                  x1={x1} y1={y1} x2={x2} y2={y2}
                  stroke={meta.color}
                  strokeWidth="1.5"
                  strokeOpacity="0.95"
                  strokeDasharray={String(leg.mode).toLowerCase() === 'sea' ? '3 1.5' : undefined}
                />
              );
            })}

            {nodes.map((node) => (
              <NodeGlyph
                key={node.id}
                node={node}
                selected={selectedNode?.id === node.id || routeNodes.has(node.id)}
                blocked={blockedIds.has(node.id)}
                onClick={setSelectedNode}
              />
            ))}
          </g>
        </svg>

        {loading && <div className="network-map-state"><Activity className="animate-pulse" size={22} /><span>Loading live network…</span></div>}
        {!loading && network?.error && (
          <div className="network-map-state network-map-error">
            <AlertTriangle size={22} />
            <div><strong>Network unavailable</strong><span>{network.error}</span></div>
          </div>
        )}

        {selectedNode && (
          <div className="network-node-inspector">
            <div className="network-node-inspector-title">
              <strong>{selectedNode.display_name}</strong>
              <button onClick={() => setSelectedNode(null)} aria-label="Close">×</button>
            </div>
            <div className="network-node-meta">
              <span>{TYPE_META[selectedNode.type]?.label || selectedNode.type}</span>
              <span>{selectedNode.country}</span>
              {selectedNode.modes?.map((mode) => (
                <span key={mode} className="network-mode-chip">{MODE_META[mode]?.label || mode}</span>
              ))}
            </div>
            {blockedIds.has(selectedNode.id) && (
              <div className="network-blocked-note"><AlertTriangle size={13} /> Blocked by active scenario</div>
            )}
          </div>
        )}

        <div className="network-map-legend">
          {Object.entries(MODE_META).filter(([mode]) => mode !== 'transfer').map(([mode, meta]) => (
            <span key={mode}><i style={{ background: meta.color }} />{meta.label}</span>
          ))}
          <span><i className="network-legend-blocked" />BLOCKED</span>
        </div>

        <div className="network-map-attribution">© OpenStreetMap contributors</div>
      </div>

      <div className="network-route-strip">
        <div className="network-route-tabs">
          {(recommendations || []).map((rec, index) => (
            <button
              key={`${routeSignature(rec)}-${index}`}
              className={selectedRouteIndex === index ? 'active' : ''}
              onClick={() => onRouteSelect?.(index)}
            >
              <span>{rec.persona}</span>
              <small>{rec.adjusted_eta}h · ${Number(rec.total_cost || 0).toLocaleString()}</small>
            </button>
          ))}
          {!recommendations?.length && <span className="network-route-empty">Generate a recommendation to highlight the selected backend route.</span>}
        </div>

        {activeScenario && (
          <div className="network-scenario-state">
            <AlertTriangle size={14} />
            <span>{activeScenario.name}</span>
            <strong>{activeScenario.closed ? 'BLOCKED' : 'IMPACTED'}</strong>
          </div>
        )}
      </div>
    </section>
  );
}
