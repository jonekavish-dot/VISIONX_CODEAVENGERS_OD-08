import React, { useState, useEffect, useCallback } from 'react';

function getApiBaseUrl() {
  if (typeof window !== 'undefined') {
    const custom = localStorage.getItem('vtrace_backend_url');
    if (custom && custom.trim()) {
      return custom.trim().replace(/\/$/, '');
    }
    // Auto-connect Vercel frontend to live Render FastAPI backend
    if (window.location.hostname.includes('vercel.app') || (!window.location.hostname.includes('onrender.com') && !window.location.hostname.includes('localhost') && !window.location.hostname.includes('127.0.0.1'))) {
      return 'https://visionx-codeavengers-od-08.onrender.com';
    }
  }
  return (import.meta.env.VITE_API_URL || '').replace(/\/$/, '');
}


function apiUrl(path) {
  return `${getApiBaseUrl()}${path}`;
}

async function apiFetch(path, options) {
  const response = await fetch(apiUrl(path), options);
  const contentType = response.headers.get('content-type') || '';
  if (!contentType.includes('application/json')) {
    const body = await response.text();
    throw new Error(
      `API returned ${response.status} ${response.statusText} instead of JSON` +
      (body ? `: ${body.slice(0, 160)}` : '')
    );
  }
  return response;
}

// Safe image helper to prevent broken images
function getImageUrl(path) {
  if (!path) return null;
  if (path.startsWith('http://') || path.startsWith('https://')) return path;
  if (path.startsWith('/evidence') || path.startsWith('/scenarios')) return apiUrl(path);
  // Convert Windows backslashes
  const cleanPath = path.replace(/\\/g, '/');
  if (cleanPath.includes('/data/evidence/')) {
    const filename = cleanPath.split('/data/evidence/').pop();
    return apiUrl(`/evidence/${filename}`);
  }
  if (cleanPath.includes('/data/demo/scenarios/')) {
    const subpath = cleanPath.split('/data/demo/scenarios/').pop();
    return apiUrl(`/scenarios/${subpath}`);
  }
  return apiUrl(`/api/media?path=${encodeURIComponent(path)}`);
}

export default function App() {
  // System Telemetry State
  const [health, setHealth] = useState({ status: 'offline', runtime_device: 'cpu', models_loaded: false });
  const [summary, setSummary] = useState({
    active_vehicles: 0,
    detections: 0,
    identity_warnings: 0,
    access_alerts: 0,
    route_alerts: 0,
    unreadable_plates: 0
  });
  const [liveCameras, setLiveCameras] = useState({});
  const [alerts, setAlerts] = useState([]);
  const [latestDetection, setLatestDetection] = useState(null);
  const [scenarioStatus, setScenarioStatus] = useState(null);
  const [isRunningScenario, setIsRunningScenario] = useState(false);
  const [activeScenarioName, setActiveScenarioName] = useState('');

  // Modals state
  const [comparisonModal, setComparisonModal] = useState(null); // Comparison object
  const [historyModal, setHistoryModal] = useState(null);       // Vehicle ID or list
  const [registryModal, setRegistryModal] = useState(null);     // Plate or record
  const [alertFilter, setAlertFilter] = useState({ severity: '', type: '' });

  // Backend Connection Settings
  const [currentBackendUrl, setCurrentBackendUrl] = useState(() => getApiBaseUrl());
  const [showBackendConfigModal, setShowBackendConfigModal] = useState(false);
  const [customUrlInput, setCustomUrlInput] = useState(() => getApiBaseUrl() || 'https://visionx-codeavengers-od-08.onrender.com');
  const [testResult, setTestResult] = useState(null);
  const [isTestingUrl, setIsTestingUrl] = useState(false);

  const saveBackendUrl = (newUrl) => {
    const clean = (newUrl || '').trim().replace(/\/$/, '');
    if (clean) {
      localStorage.setItem('vtrace_backend_url', clean);
    } else {
      localStorage.removeItem('vtrace_backend_url');
    }
    setCurrentBackendUrl(clean);
    setTestResult({ success: true, message: 'Backend URL updated! Testing connection...' });
    setTimeout(() => {
      fetchDashboardAll();
    }, 300);
  };


  const testBackendConnection = async (targetUrl) => {
    setIsTestingUrl(true);
    setTestResult(null);
    const clean = (targetUrl || '').trim().replace(/\/$/, '');
    const urlToTest = clean ? `${clean}/api/health` : '/api/health';

    let attempts = 0;
    const maxAttempts = 3;
    let lastError = null;

    while (attempts < maxAttempts) {
      attempts++;
      if (attempts > 1) {
        setTestResult({
          success: false,
          message: `Attempt ${attempts}/${maxAttempts}: Render backend waking up from sleep (cold boot)... please wait`
        });
      }
      try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 12000);
        const res = await fetch(urlToTest, { signal: controller.signal });
        clearTimeout(timeoutId);

        if (res.ok) {
          const data = await res.json();
          setTestResult({
            success: true,
            message: `Connected successfully! Device: ${data.runtime_device || 'CPU'}, Status: ${data.status}`
          });
          setIsTestingUrl(false);
          return;
        } else {
          lastError = `Server returned HTTP ${res.status} ${res.statusText}`;
        }
      } catch (err) {
        lastError = err.name === 'AbortError' ? 'Connection timed out (Render cold booting)' : err.message;
      }
      if (attempts < maxAttempts) {
        await new Promise(r => setTimeout(r, 2000));
      }
    }

    setTestResult({
      success: false,
      message: `Connection failed: ${lastError}. Make sure Render backend is active.`
    });
    setIsTestingUrl(false);
  };


  // ==================== LIVE INTERNET CAMERA STATE ====================
  const [youtubeUrl, setYoutubeUrl] = useState('https://www.youtube.com/watch?v=tmMrGbBOi1U');
  const [youtubeStatus, setYoutubeStatus] = useState({
    status: 'OFFLINE',
    title: 'Public YouTube Stream',
    is_live: false,
    fps: 0,
    current_frame: 0,
    processed_count: 0,
    detections_count: 0,
    last_error: null,
    stream_type: 'PUBLIC_INTERNET_STREAM',
    label: 'PUBLIC INTERNET STREAM (Not Construction Site CCTV)'
  });
  const [youtubeFrameTs, setYoutubeFrameTs] = useState(Date.now());

  const [isYoutubeLoading, setIsYoutubeLoading] = useState(false);


  const handleStartYoutube = async () => {
    if (!youtubeUrl.trim()) return;
    setIsYoutubeLoading(true);
    setYoutubeStatus(prev => ({ ...prev, status: 'CONNECTING', last_error: null }));
    try {
      const res = await apiFetch('/api/live/youtube/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: youtubeUrl.trim() })
      });
      const data = await res.json();
      if (!res.ok) {
        setYoutubeStatus(prev => ({
          ...prev,
          status: 'YOUTUBE_STREAM_UNAVAILABLE',
          last_error: data.detail || 'Failed to connect'
        }));
      } else {
        setYoutubeStatus(prev => ({ ...prev, status: data.status || 'CONNECTING' }));
      }
    } catch (err) {
      setYoutubeStatus(prev => ({
        ...prev,
        status: 'YOUTUBE_STREAM_UNAVAILABLE',
        last_error: err.message
      }));
    } finally {
      setIsYoutubeLoading(false);
    }
  };

  const handleStopYoutube = async () => {
    setIsYoutubeLoading(true);
    try {
      await apiFetch('/api/live/youtube/stop', { method: 'POST' });
      setYoutubeStatus(prev => ({ ...prev, status: 'OFFLINE' }));
    } catch (err) {
      console.error('Error stopping YouTube stream:', err);
    } finally {
      setIsYoutubeLoading(false);
    }
  };

  const [consecutiveFailures, setConsecutiveFailures] = useState(0);


  // Single-fetch Consolidated Dashboard Telemetry Polling (Optimized for Render Free Tier)
  const fetchDashboardAll = useCallback(async () => {
    try {
      let alertParams = '?alert_limit=15';
      if (alertFilter.severity) alertParams += `&severity=${alertFilter.severity}`;
      if (alertFilter.type) alertParams += `&alert_type=${alertFilter.type}`;

      let res = await apiFetch(`/api/dashboard/all${alertParams}`);

      // Fallback to same-origin if custom URL fails but same-origin succeeds
      if (!res.ok && getApiBaseUrl()) {
        res = await fetch(`/api/dashboard/all${alertParams}`);
        if (res.ok) {
          localStorage.removeItem('vtrace_backend_url');
          setCurrentBackendUrl('');
        }
      }

      if (res.ok) {
        const data = await res.json();
        if (data.health) setHealth(data.health);
        if (data.summary) setSummary(data.summary);
        if (data.live) setLiveCameras(data.live);
        if (data.latest_detection !== undefined) setLatestDetection(data.latest_detection);
        if (data.alerts) setAlerts(data.alerts);
        if (data.youtube) {
          setYoutubeStatus(data.youtube);
          if (data.youtube.status === 'CONNECTED' || data.youtube.status === 'RECONNECTING') {
            setYoutubeFrameTs(Date.now());
          }
        }
        setConsecutiveFailures(0);
      } else {
        throw new Error(`HTTP ${res.status}`);
      }
    } catch (err) {
      setConsecutiveFailures(prev => {
        const next = prev + 1;
        if (next < 3) {
          setHealth(old => ({ ...old, status: 'reconnecting' }));
        } else {
          setHealth(old => ({ ...old, status: 'offline' }));
        }
        return next;
      });
    }
  }, [alertFilter]);

  // Periodic Telemetry Polling (3000ms idle, 2000ms when scenario running)
  useEffect(() => {
    fetchDashboardAll();
    const pollInterval = isRunningScenario ? 2000 : 3000;
    const interval = setInterval(() => {
      fetchDashboardAll();
    }, pollInterval);
    return () => clearInterval(interval);
  }, [fetchDashboardAll, isRunningScenario]);


  // 3. Demo Scenario Trigger
  const triggerScenario = async (scenarioName) => {
    setIsRunningScenario(true);
    setActiveScenarioName(scenarioName);
    try {
      const res = await apiFetch('/api/demo/scenario/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scenario: scenarioName })
      });
      const data = await res.json();
      setScenarioStatus(data);
      await fetchDashboardAll();

      // Automatically pop up evidence comparison modal for identity mismatch & plate swap
      if (data.comparison) {
        setComparisonModal(data.comparison);
      }
    } catch (err) {
      console.error('Scenario execution failed:', err);
    } finally {
      setIsRunningScenario(false);
    }
  };

  // 4. Demo Reset
  const handleResetDemo = async () => {
    try {
      await apiFetch('/api/demo/reset', { method: 'POST' });
      setComparisonModal(null);
      setHistoryModal(null);
      setScenarioStatus(null);
      await fetchDashboardAll();
    } catch (err) {

      console.error('Failed to reset demo data:', err);
    }
  };

  // 5. Open Vehicle Comparison View
  const openComparisonForVehicle = async (vehicleId) => {
    try {
      const res = await apiFetch(`/api/vehicles/${vehicleId}/comparison`);
      if (res.ok) {
        const compData = await res.json();
        setComparisonModal(compData);
      } else {
        alert(`No comparative observation data found for vehicle ${vehicleId}.`);
      }
    } catch (err) {
      console.error('Failed to load comparison:', err);
    }
  };

  // 6. Open Vehicle Observation History
  const openHistoryForVehicle = async (vehicleId) => {
    try {
      const res = await apiFetch(`/api/vehicles/${vehicleId}/history`);
      if (res.ok) {
        const historyData = await res.json();
        setHistoryModal({ vehicleId, records: historyData });
      }
    } catch (err) {
      console.error('Failed to load vehicle history:', err);
    }
  };

  // 7. Open Demo Registry Modal
  const openRegistryModal = async (plate) => {
    try {
      const res = await apiFetch(`/api/registry/vehicle/${encodeURIComponent(plate || 'TN01AB1234')}`);
      if (res.ok) {
        const regData = await res.json();
        setRegistryModal(regData);
      } else {
        setRegistryModal({ plate: plate || 'UNKNOWN', notFound: true });
      }
    } catch (err) {
      console.error('Failed to fetch registry record:', err);
    }
  };

  // Check if there is an active identity mismatch alert
  const latestMismatchAlert = alerts.find(
    (a) => a.type === 'POSSIBLE_IDENTITY_MISMATCH' || a.type === 'POSSIBLE_PLATE_SWAP'
  );

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans">
      {/* ==================== TOP HEADER ==================== */}
      <header className="bg-slate-900/90 border-b border-slate-800 px-6 py-3.5 sticky top-0 z-40 backdrop-blur flex items-center justify-between shadow-lg">
        <div className="flex items-center space-x-4">
          <div className="flex items-center space-x-2">
            <div className="w-8 h-8 rounded-lg bg-blue-600/20 border border-blue-500/40 flex items-center justify-center text-blue-400 font-bold text-lg">
              V
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <span className="font-mono text-base font-bold tracking-wider text-white">IVACS V-TRACE</span>
                <span className="text-[10px] font-mono uppercase px-1.5 py-0.5 rounded bg-blue-500/20 text-blue-300 border border-blue-500/30">
                  OD-08 MVP
                </span>
              </div>
              <p className="text-xs text-slate-400 hidden sm:block">Vehicle Trust, Route & Evidence Engine</p>
            </div>
          </div>
        </div>

        {/* Status Indicators & Demo Badge */}
        <div className="flex items-center space-x-3">
          {/* Online / Reconnecting / Offline status */}
          <div className="flex items-center space-x-1.5 px-2.5 py-1 rounded-full bg-slate-800/80 border border-slate-700 text-xs">
            <span className={`w-2 h-2 rounded-full ${
              health.status === 'healthy' ? 'bg-emerald-400 animate-pulse' :
              health.status === 'reconnecting' ? 'bg-amber-400 animate-ping' : 'bg-rose-500'
            }`}></span>
            <span className="font-mono font-medium text-slate-200">
              {health.status === 'healthy' ? 'ONLINE' : health.status === 'reconnecting' ? 'RECONNECTING...' : 'OFFLINE'}
            </span>
            <span className="text-slate-500 text-[10px]">({(health.runtime_device || 'cpu').toUpperCase()})</span>
          </div>


          {/* Explicit DEMO DATA indicator */}
          <div className="flex items-center space-x-1 px-2.5 py-1 rounded-full bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs font-mono font-semibold">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-400"></span>
            <span>DEMO DATA</span>
          </div>

          {/* Backend Settings link */}
          <button
            onClick={() => setShowBackendConfigModal(true)}
            className={`px-3 py-1 rounded border text-xs font-mono transition flex items-center space-x-1 ${
              health.status === 'healthy'
                ? 'bg-slate-800 hover:bg-slate-700 border-slate-700 text-slate-300'
                : 'bg-rose-900/40 hover:bg-rose-800/60 border-rose-700 text-rose-200 font-bold animate-pulse'
            }`}
          >
            <span>⚡ Backend Server</span>
          </button>

          {/* Quick Registry Catalog link */}
          <button
            onClick={() => openRegistryModal('TN01AB1234')}
            className="px-3 py-1 rounded bg-slate-800 hover:bg-slate-700 border border-slate-700 text-xs text-slate-300 transition"
          >
            Vehicle Registry
          </button>
        </div>
      </header>

      {/* ==================== MAIN CONTENT CONTAINER ==================== */}
      <main className="flex-1 p-5 max-w-[1700px] w-full mx-auto space-y-5">

        {/* OFFLINE BACKEND CONNECTION WARNING BANNER */}
        {health.status !== 'healthy' && (
          <div className="bg-rose-950/80 border border-rose-800/80 rounded-xl p-4 flex flex-col md:flex-row items-center justify-between gap-3 shadow-lg">
            <div className="flex items-center space-x-3">
              <div className="w-3 h-3 rounded-full bg-rose-500 animate-ping"></div>
              <div>
                <h4 className="font-mono font-bold text-rose-200 text-sm">BACKEND OFFLINE / DISCONNECTED</h4>
                <p className="text-xs text-rose-300/80">
                  Vercel static frontend is not connected to FastAPI backend. Set backend server URL below or connect to your Render service.
                </p>
              </div>
            </div>
            <div className="flex items-center space-x-2 shrink-0">
              <button
                onClick={() => saveBackendUrl('https://visionx-codeavengers-od-08.onrender.com')}
                className="px-3 py-1.5 rounded bg-blue-600 hover:bg-blue-500 text-white font-mono text-xs font-semibold transition"
              >
                Render Backend
              </button>
              <button
                onClick={() => saveBackendUrl('http://localhost:8000')}
                className="px-3 py-1.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-200 font-mono text-xs transition border border-slate-700"
              >
                Local Server (8000)
              </button>
              <button
                onClick={() => setShowBackendConfigModal(true)}
                className="px-3 py-1.5 rounded bg-rose-800 hover:bg-rose-700 text-rose-100 font-mono text-xs font-semibold transition"
              >
                Custom URL
              </button>
            </div>
          </div>
        )}
        
        {/* ==================== 1. TOP KPI TELEMETRY CARDS ==================== */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3.5">
          <div className="bg-slate-900/70 border border-slate-800/90 rounded-xl p-3.5 flex flex-col justify-between hover:border-slate-700 transition">
            <span className="text-[11px] font-mono text-slate-400 uppercase tracking-wider">ACTIVE VEHICLES</span>
            <div className="flex items-baseline space-x-2 mt-1">
              <span className="text-2xl font-bold font-mono text-white">{summary.active_vehicles}</span>
              <span className="text-[10px] text-slate-500">identities</span>
            </div>
          </div>

          <div className="bg-slate-900/70 border border-slate-800/90 rounded-xl p-3.5 flex flex-col justify-between hover:border-slate-700 transition">
            <span className="text-[11px] font-mono text-slate-400 uppercase tracking-wider">DETECTIONS</span>
            <div className="flex items-baseline space-x-2 mt-1">
              <span className="text-2xl font-bold font-mono text-cyan-400">{summary.detections}</span>
              <span className="text-[10px] text-slate-500">frames</span>
            </div>
          </div>

          <div className={`rounded-xl p-3.5 flex flex-col justify-between border transition ${
            summary.identity_warnings > 0
              ? 'bg-rose-950/30 border-rose-600/40 text-rose-300'
              : 'bg-slate-900/70 border-slate-800/90 text-slate-400'
          }`}>
            <span className="text-[11px] font-mono uppercase tracking-wider">IDENTITY WARNINGS</span>
            <div className="flex items-baseline space-x-2 mt-1">
              <span className={`text-2xl font-bold font-mono ${summary.identity_warnings > 0 ? 'text-rose-400' : 'text-slate-200'}`}>
                {summary.identity_warnings}
              </span>
              <span className="text-[10px] text-slate-500">mismatches</span>
            </div>
          </div>

          <div className={`rounded-xl p-3.5 flex flex-col justify-between border transition ${
            summary.access_alerts > 0
              ? 'bg-amber-950/30 border-amber-600/40 text-amber-300'
              : 'bg-slate-900/70 border-slate-800/90 text-slate-400'
          }`}>
            <span className="text-[11px] font-mono uppercase tracking-wider">ACCESS ALERTS</span>
            <div className="flex items-baseline space-x-2 mt-1">
              <span className={`text-2xl font-bold font-mono ${summary.access_alerts > 0 ? 'text-amber-400' : 'text-slate-200'}`}>
                {summary.access_alerts}
              </span>
              <span className="text-[10px] text-slate-500">permits</span>
            </div>
          </div>

          <div className="bg-slate-900/70 border border-slate-800/90 rounded-xl p-3.5 flex flex-col justify-between hover:border-slate-700 transition">
            <span className="text-[11px] font-mono text-slate-400 uppercase tracking-wider">ROUTE ALERTS</span>
            <div className="flex items-baseline space-x-2 mt-1">
              <span className="text-2xl font-bold font-mono text-indigo-400">{summary.route_alerts}</span>
              <span className="text-[10px] text-slate-500">anomalies</span>
            </div>
          </div>

          <div className="bg-slate-900/70 border border-slate-800/90 rounded-xl p-3.5 flex flex-col justify-between hover:border-slate-700 transition">
            <span className="text-[11px] font-mono text-slate-400 uppercase tracking-wider">UNREADABLE PLATES</span>
            <div className="flex items-baseline space-x-2 mt-1">
              <span className="text-2xl font-bold font-mono text-slate-300">{summary.unreadable_plates}</span>
              <span className="text-[10px] text-slate-500">continuity</span>
            </div>
          </div>
        </div>

        {/* ==================== 2. CONTROLLED DEMO SCENARIO BAR ==================== */}
        <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-4 shadow-sm">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
            <div>
              <span className="text-xs font-mono uppercase tracking-wider text-slate-400 flex items-center space-x-1.5">
                <span className="w-2 h-2 rounded-full bg-blue-500"></span>
                <span>HACKATHON DEMO CONTROLS (REAL NEURAL EMBEDDINGS — ZERO LLM)</span>
              </span>
              <p className="text-xs text-slate-500 mt-0.5">
                Trigger controlled scenario state machine to demonstrate identity consistency & mismatch detection.
              </p>
            </div>

            {/* 5 Scenario Buttons */}
            <div className="flex flex-wrap items-center gap-2">
              <button
                disabled={isRunningScenario}
                onClick={() => triggerScenario('NORMAL_REPEAT')}
                className="px-3 py-1.5 rounded-lg text-xs font-mono font-semibold bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 transition flex items-center space-x-1.5 disabled:opacity-50"
              >
                <span>NORMAL REPEAT</span>
              </button>

              <button
                disabled={isRunningScenario}
                onClick={() => triggerScenario('IDENTITY_MISMATCH')}
                className="px-3 py-1.5 rounded-lg text-xs font-mono font-semibold bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 border border-rose-500/30 transition flex items-center space-x-1.5 disabled:opacity-50"
              >
                <span>IDENTITY MISMATCH</span>
              </button>

              <button
                disabled={isRunningScenario}
                onClick={() => triggerScenario('PLATE_SWAP')}
                className="px-3 py-1.5 rounded-lg text-xs font-mono font-semibold bg-purple-500/10 hover:bg-purple-500/20 text-purple-400 border border-purple-500/30 transition flex items-center space-x-1.5 disabled:opacity-50"
              >
                <span>PLATE SWAP</span>
              </button>

              <button
                disabled={isRunningScenario}
                onClick={() => triggerScenario('PLATE_UNREADABLE')}
                className="px-3 py-1.5 rounded-lg text-xs font-mono font-semibold bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition flex items-center space-x-1.5 disabled:opacity-50"
              >
                <span>UNREADABLE PLATE</span>
              </button>

              <button
                disabled={isRunningScenario}
                onClick={handleResetDemo}
                className="px-3 py-1.5 rounded-lg text-xs font-mono font-semibold bg-slate-900 hover:bg-rose-950/40 text-slate-400 hover:text-rose-300 border border-slate-700 hover:border-rose-600/40 transition"
              >
                <span>RESET DEMO</span>
              </button>
            </div>
          </div>

          {/* Scenario Execution Telemetry Banner */}
          {isRunningScenario && (
            <div className="mt-3 pt-3 border-t border-slate-800/80 flex items-center space-x-2 text-xs text-blue-400 font-mono animate-pulse">
              <span className="w-2 h-2 rounded-full bg-blue-500"></span>
              <span>Executing {activeScenarioName}... processing real ResNet18 embeddings through decision rules...</span>
            </div>
          )}
        </div>

        {/* ==================== 2B. LIVE INTERNET CAMERA INPUT (PUBLIC STREAM) ==================== */}
        <div className="bg-slate-900/90 border border-indigo-500/30 rounded-xl p-4 shadow-lg space-y-3">
          <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3">
            <div>
              <div className="flex items-center space-x-2">
                <span className="w-2.5 h-2.5 rounded-full bg-indigo-500"></span>
                <span className="font-mono text-sm font-bold text-white tracking-wide">
                  LIVE INTERNET CAMERA (PUBLIC INTERNET STREAM)
                </span>
                {/* Status Badge */}
                <span className={`px-2.5 py-0.5 rounded-full text-[11px] font-mono font-semibold uppercase tracking-wider flex items-center space-x-1.5 ${
                  youtubeStatus.status === 'CONNECTED'
                    ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                    : youtubeStatus.status === 'CONNECTING'
                    ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40 animate-pulse'
                    : youtubeStatus.status === 'RECONNECTING'
                    ? 'bg-orange-500/20 text-orange-300 border border-orange-500/40 animate-pulse'
                    : youtubeStatus.status === 'YOUTUBE_STREAM_UNAVAILABLE'
                    ? 'bg-rose-500/20 text-rose-300 border border-rose-500/40'
                    : 'bg-slate-800 text-slate-400 border border-slate-700'
                }`}>
                  <span className={`w-1.5 h-1.5 rounded-full ${
                    youtubeStatus.status === 'CONNECTED' ? 'bg-emerald-400 animate-ping' :
                    youtubeStatus.status === 'CONNECTING' || youtubeStatus.status === 'RECONNECTING' ? 'bg-amber-400' :
                    youtubeStatus.status === 'YOUTUBE_STREAM_UNAVAILABLE' ? 'bg-rose-400' : 'bg-slate-500'
                  }`}></span>
                  <span>{youtubeStatus.status}</span>
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-1">
                <strong className="text-indigo-300">PUBLIC INTERNET STREAM</strong> — Public Traffic Camera (Not Construction Site CCTV).
                Ingested directly via <code className="text-slate-300">yt-dlp</code> into native YOLOv8 + EasyOCR + ResNet18 pipeline.
              </p>
            </div>

            {/* Input & Connect Action Bar */}
            <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2">
              <div className="relative flex-1 sm:w-[380px]">
                <input
                  type="text"
                  value={youtubeUrl}
                  onChange={(e) => setYoutubeUrl(e.target.value)}
                  placeholder="https://www.youtube.com/watch?v=..."
                  className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-slate-200 font-mono focus:outline-none focus:border-indigo-500"
                />
              </div>

              {youtubeStatus.status === 'CONNECTED' || youtubeStatus.status === 'CONNECTING' ? (
                <button
                  onClick={handleStopYoutube}
                  disabled={isYoutubeLoading}
                  className="px-4 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-500 text-white font-mono text-xs font-semibold shadow transition disabled:opacity-50"
                >
                  DISCONNECT
                </button>
              ) : (
                <button
                  onClick={handleStartYoutube}
                  disabled={isYoutubeLoading}
                  className="px-4 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-mono text-xs font-semibold shadow transition disabled:opacity-50 flex items-center space-x-1.5 justify-center"
                >
                  <span>{isYoutubeLoading ? 'CONNECTING...' : 'CONNECT'}</span>
                </button>
              )}
            </div>
          </div>

          {/* Stream Player & Real-Time Telemetry Bar (Visible when active) */}
          {(youtubeStatus.status === 'CONNECTED' || youtubeStatus.status === 'CONNECTING' || youtubeStatus.status === 'RECONNECTING') && (
            <div className="mt-3 pt-3 border-t border-slate-800 grid grid-cols-1 lg:grid-cols-3 gap-4 items-center">
              <div className="lg:col-span-2 relative bg-black rounded-lg overflow-hidden border border-slate-800 aspect-video flex items-center justify-center">
                <img
                  src={apiUrl(`/api/live/youtube/frame?t=${youtubeFrameTs}`)}
                  alt="Live Internet Camera"
                  className="w-full h-full object-contain"
                />
                <div className="absolute top-2 left-2 px-2 py-1 rounded bg-black/70 backdrop-blur border border-slate-700 text-[11px] font-mono text-white flex items-center space-x-1.5">
                  <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
                  <span className="font-bold">LIVE INTERNET STREAM</span>
                </div>
                <div className="absolute bottom-2 right-2 px-2 py-0.5 rounded bg-black/70 font-mono text-[10px] text-slate-300">
                  {youtubeStatus.fps} FPS
                </div>
              </div>

              {/* Stream Telemetry Card */}
              <div className="bg-slate-950/70 border border-slate-800/90 rounded-lg p-3.5 space-y-2.5 text-xs font-mono">
                <div className="text-slate-300 font-bold border-b border-slate-800 pb-1.5 truncate">
                  {youtubeStatus.title}
                </div>
                <div className="flex justify-between text-slate-400">
                  <span>Stream Source:</span>
                  <span className="text-indigo-300 font-semibold">YouTube Live HLS</span>
                </div>
                <div className="flex justify-between text-slate-400">
                  <span>Processed Frames:</span>
                  <span className="text-white font-bold">{youtubeStatus.processed_count}</span>
                </div>
                <div className="flex justify-between text-slate-400">
                  <span>Live Vehicles Detected:</span>
                  <span className="text-emerald-400 font-bold">{youtubeStatus.detections_count}</span>
                </div>
                <div className="flex justify-between text-slate-400">
                  <span>Pipeline Latency:</span>
                  <span className="text-cyan-400 font-semibold">{youtubeStatus.fps > 0 ? `${Math.round(1000 / youtubeStatus.fps)}ms` : 'Calculating...'}</span>
                </div>
                <div className="pt-2 border-t border-slate-800/80 text-[10px] text-slate-500 italic">
                  Note: Frames are streamed dynamically from the internet without caching whole files.
                </div>
              </div>
            </div>
          )}

          {/* Error Banner if stream unavailable */}
          {youtubeStatus.status === 'YOUTUBE_STREAM_UNAVAILABLE' && (
            <div className="mt-2 p-2.5 rounded-lg bg-rose-950/30 border border-rose-500/40 text-xs font-mono text-rose-300 flex items-center justify-between">
              <span>Error: {youtubeStatus.last_error || 'YOUTUBE_STREAM_UNAVAILABLE'}</span>
              <button onClick={handleStartYoutube} className="text-[11px] underline hover:text-white">Retry Connection</button>
            </div>
          )}
        </div>

        {/* ==================== 3. PROMINENT IDENTITY ALERT BANNER ==================== */}
        {latestMismatchAlert && (
          <div className="bg-rose-950/40 border-2 border-rose-600/60 rounded-xl p-4 shadow-xl flex flex-col md:flex-row md:items-center justify-between gap-4 animate-in fade-in duration-300">
            <div className="flex items-start space-x-3.5">
              <div className="w-10 h-10 rounded-lg bg-rose-600/20 border border-rose-500/40 flex items-center justify-center text-rose-400 shrink-0 font-bold text-lg">
                !
              </div>
              <div>
                <div className="flex items-center space-x-2">
                  <span className="text-sm font-mono font-bold tracking-wide text-rose-300">
                    {latestMismatchAlert.title}
                  </span>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-rose-600 text-white font-semibold">
                    {latestMismatchAlert.severity}
                  </span>
                </div>
                <p className="text-xs text-slate-300 mt-1">{latestMismatchAlert.reason}</p>
                <div className="flex items-center space-x-4 mt-2 text-xs font-mono text-slate-400">
                  <span>Plate: <strong className="text-white">{latestMismatchAlert.plate || 'N/A'}</strong></span>
                  <span>Camera: <strong className="text-white">{latestMismatchAlert.camera_id}</strong></span>
                  <span>Zone: <strong className="text-white">{latestMismatchAlert.zone}</strong></span>
                  <span className="text-rose-400 font-semibold">{latestMismatchAlert.action_required}</span>
                </div>
              </div>
            </div>

            <div className="flex items-center space-x-2 shrink-0">
              {latestMismatchAlert.vehicle_id && (
                <button
                  onClick={() => openComparisonForVehicle(latestMismatchAlert.vehicle_id)}
                  className="px-4 py-2 rounded-lg bg-rose-600 hover:bg-rose-500 text-white font-mono text-xs font-semibold shadow transition"
                >
                  VIEW EVIDENCE
                </button>
              )}
              {latestMismatchAlert.vehicle_id && (
                <button
                  onClick={() => openHistoryForVehicle(latestMismatchAlert.vehicle_id)}
                  className="px-3 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 font-mono text-xs transition"
                >
                  VIEW VEHICLE HISTORY
                </button>
              )}
            </div>
          </div>
        )}

        {/* ==================== 4. LIVE CCTV 4-CAMERA GRID ==================== */}
        <div>
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center space-x-2">
              <span className="text-sm font-mono font-bold text-white tracking-wider">LIVE CCTV SENSOR GRID</span>
              <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/30">
                DEMO DATA
              </span>
            </div>
            <span className="text-xs text-slate-500 font-mono">4 SENSORS CONFIGURED (CAM-01 TO CAM-04)</span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {['CAM-01', 'CAM-02', 'CAM-03', 'CAM-04'].map((camId) => {
              const cam = liveCameras[camId] || {
                camera_id: camId,
                camera_name: camId === 'CAM-01' ? 'Gate Entrance' : camId === 'CAM-02' ? 'Material Yard' : camId === 'CAM-03' ? 'Active Zone' : 'Gate Exit',
                zone: camId === 'CAM-01' ? 'GATE_IN' : camId === 'CAM-02' ? 'MATERIAL_YARD' : camId === 'CAM-03' ? 'ACTIVE_ZONE' : 'GATE_OUT',
                status: 'IDLE',
                plate: 'IDLE'
              };

              const imgSrc = getImageUrl(cam.annotated_frame_path || cam.frame_path || cam.vehicle_crop_path);

              return (
                <div key={camId} className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden flex flex-col shadow-md">
                  {/* Card Header */}
                  <div className="px-3 py-2 bg-slate-800/60 border-b border-slate-800 flex items-center justify-between">
                    <div className="flex items-center space-x-1.5">
                      <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
                      <span className="font-mono text-xs font-bold text-white">{cam.camera_id}</span>
                      <span className="text-xs text-slate-400 truncate">({cam.camera_name})</span>
                    </div>
                    <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-700/60 text-slate-300">
                      {cam.zone}
                    </span>
                  </div>

                  {/* Camera Frame Preview */}
                  <div className="aspect-video bg-slate-950 relative flex items-center justify-center overflow-hidden border-b border-slate-800/80">
                    {imgSrc ? (
                      <img
                        src={imgSrc}
                        alt={`${cam.camera_id} stream`}
                        className="w-full h-full object-cover object-center"
                        onError={(e) => {
                          e.target.style.display = 'none';
                        }}
                      />
                    ) : (
                      <div className="flex flex-col items-center justify-center text-slate-600 space-y-1">
                        <span className="text-xs font-mono">[STANDBY FEED]</span>
                        <span className="text-[10px] text-slate-700">Awaiting detection trigger</span>
                      </div>
                    )}
                    {/* Live overlay tag */}
                    <div className="absolute top-2 left-2 px-1.5 py-0.5 rounded bg-black/60 backdrop-blur text-[10px] font-mono text-emerald-400 flex items-center space-x-1">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-ping"></span>
                      <span>FEED ONLINE</span>
                    </div>
                  </div>

                  {/* Card Footer Telemetry */}
                  <div className="p-3 bg-slate-900/90 text-xs space-y-1.5">
                    <div className="flex items-center justify-between font-mono">
                      <span className="text-slate-400">Observed Plate:</span>
                      <span className={`font-bold ${cam.plate && cam.plate !== 'IDLE' ? 'text-amber-400' : 'text-slate-500'}`}>
                        {cam.plate || 'NO_PLATE'}
                      </span>
                    </div>
                    <div className="flex items-center justify-between font-mono text-[11px]">
                      <span className="text-slate-400">Vehicle Class:</span>
                      <span className="text-slate-300 uppercase">{cam.vehicle_class || 'UNKNOWN'}</span>
                    </div>
                    <div className="flex items-center justify-between font-mono text-[11px]">
                      <span className="text-slate-400">Event Signal:</span>
                      <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${
                        cam.identity_event === 'POSSIBLE_IDENTITY_MISMATCH'
                          ? 'bg-rose-500/20 text-rose-300 border border-rose-500/30'
                          : cam.identity_event === 'SAME_VEHICLE'
                          ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                          : 'bg-slate-800 text-slate-400'
                      }`}>
                        {cam.identity_event || cam.status || 'READY'}
                      </span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* ==================== 5. LATEST VEHICLE TRUST PROFILE & SECURITY ALERTS ==================== */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
          
          {/* LATEST VEHICLE PANEL (Left 1 Col) */}
          <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-4 flex flex-col justify-between shadow-md">
            <div>
              <div className="flex items-center justify-between border-b border-slate-800 pb-2.5 mb-3">
                <span className="text-xs font-mono font-bold text-white uppercase tracking-wider">
                  LATEST DETECTED VEHICLE PROFILE
                </span>
                <span className="text-[10px] font-mono text-slate-500">LIVE ANPR + VISUAL ID</span>
              </div>

              {latestDetection ? (
                <div className="space-y-3">
                  {/* Plate display */}
                  <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 flex items-center justify-between">
                    <div>
                      <span className="text-[10px] font-mono text-slate-400 uppercase">License Plate</span>
                      <div className="text-xl font-bold font-mono text-amber-300 tracking-wider">
                        {latestDetection.plate || latestDetection.raw_plate || 'UNREADABLE'}
                      </div>
                    </div>
                    <div className="text-right font-mono text-xs">
                      <span className="text-slate-400 text-[10px] block">Vehicle ID</span>
                      <span className="font-bold text-white">{latestDetection.vehicle_id || 'PENDING'}</span>
                    </div>
                  </div>

                  {/* Attributes Table */}
                  <div className="space-y-1.5 text-xs font-mono">
                    <div className="flex justify-between py-1 border-b border-slate-800/60">
                      <span className="text-slate-400">Class:</span>
                      <span className="text-white uppercase">{latestDetection.vehicle_class || 'N/A'}</span>
                    </div>
                    <div className="flex justify-between py-1 border-b border-slate-800/60">
                      <span className="text-slate-400">Visual Similarity:</span>
                      <span className="text-cyan-400 font-bold">
                        {latestDetection.visual_similarity != null ? latestDetection.visual_similarity.toFixed(2) : 'N/A'}
                      </span>
                    </div>
                    <div className="flex justify-between py-1 border-b border-slate-800/60">
                      <span className="text-slate-400">Identity Decision:</span>
                      <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${
                        latestDetection.identity_event === 'POSSIBLE_IDENTITY_MISMATCH'
                          ? 'bg-rose-500/20 text-rose-300'
                          : latestDetection.identity_event === 'SAME_VEHICLE'
                          ? 'bg-emerald-500/20 text-emerald-300'
                          : 'bg-slate-800 text-slate-300'
                      }`}>
                        {latestDetection.identity_event || 'NEW_VEHICLE'}
                      </span>
                    </div>
                    <div className="flex justify-between py-1 border-b border-slate-800/60">
                      <span className="text-slate-400">Camera / Zone:</span>
                      <span className="text-slate-300">{latestDetection.camera_id} ({latestDetection.zone})</span>
                    </div>
                    <div className="flex justify-between py-1">
                      <span className="text-slate-400">Timestamp:</span>
                      <span className="text-slate-400 text-[11px] truncate max-w-[180px]">{latestDetection.timestamp}</span>
                    </div>
                  </div>

                  {/* Crops Preview */}
                  <div className="grid grid-cols-2 gap-2 pt-2">
                    {latestDetection.vehicle_crop_path && (
                      <div className="rounded border border-slate-800 bg-black/40 overflow-hidden text-center">
                        <img
                          src={getImageUrl(latestDetection.vehicle_crop_path)}
                          alt="Vehicle Crop"
                          className="h-20 w-full object-cover"
                        />
                        <span className="text-[9px] font-mono text-slate-400 block py-0.5">VEHICLE CROP</span>
                      </div>
                    )}
                    {latestDetection.plate_crop_path && (
                      <div className="rounded border border-slate-800 bg-black/40 overflow-hidden text-center">
                        <img
                          src={getImageUrl(latestDetection.plate_crop_path)}
                          alt="Plate Crop"
                          className="h-20 w-full object-contain p-1"
                        />
                        <span className="text-[9px] font-mono text-slate-400 block py-0.5">PLATE CROP</span>
                      </div>
                    )}
                  </div>
                </div>
              ) : (
                <div className="py-8 text-center text-slate-500 font-mono text-xs">
                  Awaiting vehicle sighting from camera feed...
                </div>
              )}
            </div>

            {/* Bottom Actions */}
            {latestDetection?.vehicle_id && (
              <div className="pt-3 border-t border-slate-800 flex gap-2">
                <button
                  onClick={() => openComparisonForVehicle(latestDetection.vehicle_id)}
                  className="flex-1 py-1.5 rounded bg-blue-600/20 hover:bg-blue-600/30 text-blue-400 border border-blue-500/40 text-xs font-mono font-semibold transition"
                >
                  Inspect Evidence
                </button>
                <button
                  onClick={() => openHistoryForVehicle(latestDetection.vehicle_id)}
                  className="px-3 py-1.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 text-xs font-mono transition"
                >
                  History
                </button>
              </div>
            )}
          </div>

          {/* SECURITY & IDENTITY ALERT HISTORY (Right 2 Cols) */}
          <div className="lg:col-span-2 bg-slate-900/80 border border-slate-800 rounded-xl p-4 flex flex-col shadow-md">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between border-b border-slate-800 pb-2.5 mb-3 gap-2">
              <span className="text-xs font-mono font-bold text-white uppercase tracking-wider">
                SECURITY ALERT AUDIT LOG
              </span>

              {/* Filters */}
              <div className="flex items-center space-x-2 text-xs font-mono">
                <select
                  value={alertFilter.severity}
                  onChange={(e) => setAlertFilter((prev) => ({ ...prev, severity: e.target.value }))}
                  className="bg-slate-800 border border-slate-700 rounded px-2 py-1 text-slate-200 text-xs"
                >
                  <option value="">All Severities</option>
                  <option value="CRITICAL">Critical</option>
                  <option value="WARNING">Warning</option>
                  <option value="INFO">Info</option>
                </select>

                <select
                  value={alertFilter.type}
                  onChange={(e) => setAlertFilter((prev) => ({ ...prev, type: e.target.value }))}
                  className="bg-slate-800 border border-slate-700 rounded px-2 py-1 text-slate-200 text-xs"
                >
                  <option value="">All Alert Types</option>
                  <option value="POSSIBLE_IDENTITY_MISMATCH">Identity Mismatch</option>
                  <option value="POSSIBLE_PLATE_SWAP">Plate Swap</option>
                  <option value="PERMIT_EXPIRED">Permit Expired</option>
                  <option value="UNAUTHORIZED_ZONE">Unauthorized Zone</option>
                  <option value="ROUTE_INTEGRITY_ANOMALY">Route Anomaly</option>
                </select>
              </div>
            </div>

            {/* Alert List */}
            <div className="flex-1 overflow-y-auto max-h-[360px] space-y-2 pr-1">
              {alerts.length > 0 ? (
                alerts.map((al) => (
                  <div
                    key={al.id}
                    className="p-2.5 rounded-lg bg-slate-950/60 border border-slate-800/90 hover:border-slate-700 transition flex flex-col sm:flex-row sm:items-center justify-between gap-2"
                  >
                    <div className="flex items-start space-x-2.5">
                      <span className={`w-2 h-2 rounded-full mt-1.5 shrink-0 ${
                        al.severity === 'CRITICAL' ? 'bg-rose-500' : al.severity === 'WARNING' ? 'bg-amber-400' : 'bg-blue-400'
                      }`}></span>
                      <div>
                        <div className="flex items-center space-x-2">
                          <span className="font-mono text-xs font-bold text-white">{al.title}</span>
                          <span className={`text-[9px] font-mono px-1.5 rounded ${
                            al.severity === 'CRITICAL' ? 'bg-rose-950 text-rose-300 border border-rose-800' : 'bg-amber-950 text-amber-300 border border-amber-800'
                          }`}>
                            {al.severity}
                          </span>
                        </div>
                        <p className="text-xs text-slate-400 mt-0.5 line-clamp-1">{al.reason}</p>
                        <div className="flex items-center space-x-3 text-[10px] font-mono text-slate-500 mt-1">
                          <span>Plate: <strong className="text-slate-300">{al.plate || 'N/A'}</strong></span>
                          <span>Cam: <strong className="text-slate-300">{al.camera_id}</strong></span>
                          <span>Zone: <strong className="text-slate-300">{al.zone}</strong></span>
                          <span>Time: {al.timestamp.slice(11, 19)}</span>
                        </div>
                      </div>
                    </div>

                    {al.vehicle_id && (
                      <button
                        onClick={() => openComparisonForVehicle(al.vehicle_id)}
                        className="self-end sm:self-center px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 border border-slate-700 text-[11px] font-mono text-blue-300 shrink-0 transition"
                      >
                        Evidence &gt;
                      </button>
                    )}
                  </div>
                ))
              ) : (
                <div className="py-12 text-center text-slate-500 font-mono text-xs">
                  No alerts recorded under current filter. Run a scenario to trigger anomalies.
                </div>
              )}
            </div>
          </div>
        </div>
      </main>

      {/* ==================== MODAL: SIDE-BY-SIDE EVIDENCE COMPARISON ==================== */}
      {comparisonModal && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4 overflow-y-auto">
          <div className="bg-slate-900 border-2 border-slate-700 rounded-2xl max-w-4xl w-full overflow-hidden shadow-2xl animate-in zoom-in-95 duration-200">
            {/* Modal Header */}
            <div className="px-6 py-4 bg-slate-800/80 border-b border-slate-700 flex items-center justify-between">
              <div>
                <span className="text-[10px] font-mono uppercase tracking-wider text-blue-400 font-semibold">
                  EVIDENCE COMPARISON AUDIT
                </span>
                <h3 className="text-base font-mono font-bold text-white flex items-center space-x-2">
                  <span>VEHICLE {comparisonModal.vehicle_id}</span>
                  <span className="text-slate-400">|</span>
                  <span className="text-amber-300">{comparisonModal.observed_plate || 'PLATE UNKNOWN'}</span>
                </h3>
              </div>
              <button
                onClick={() => setComparisonModal(null)}
                className="w-8 h-8 rounded-lg bg-slate-700 hover:bg-slate-600 text-slate-300 flex items-center justify-center font-bold text-lg transition"
              >
                &times;
              </button>
            </div>

            {/* Comparative View: LEFT (Current) vs RIGHT (Historical) vs CENTER (Math) */}
            <div className="p-6 space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6 items-center">
                
                {/* LEFT: Current Observation */}
                <div className="bg-slate-950 border border-slate-800 rounded-xl p-3 flex flex-col space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-mono text-rose-400 font-bold uppercase">CURRENT SIGHTING</span>
                    <span className="text-[10px] font-mono text-slate-500">{comparisonModal.camera_id}</span>
                  </div>

                  <div className="aspect-video bg-black rounded-lg overflow-hidden border border-slate-800">
                    <img
                      src={getImageUrl(comparisonModal.current_vehicle_image)}
                      alt="Current Vehicle"
                      className="w-full h-full object-cover"
                    />
                  </div>

                  {comparisonModal.current_plate_image && (
                    <div className="h-12 bg-black rounded-lg overflow-hidden border border-slate-800 flex items-center justify-center p-1">
                      <img
                        src={getImageUrl(comparisonModal.current_plate_image)}
                        alt="Current Plate"
                        className="max-h-full object-contain"
                      />
                    </div>
                  )}

                  <div className="text-[11px] font-mono text-slate-400 pt-1">
                    Plate: <strong className="text-white">{comparisonModal.observed_plate || 'N/A'}</strong>
                  </div>
                </div>

                {/* CENTER: Similarity & Decision Math */}
                <div className="flex flex-col items-center justify-center text-center px-2 py-4 bg-slate-950/60 border border-slate-800 rounded-xl space-y-3">
                  <span className="text-[10px] font-mono text-slate-400 uppercase tracking-wider font-semibold">
                    RESNET18 COSINE SIMILARITY
                  </span>

                  <div className="relative flex items-center justify-center">
                    <div className={`w-28 h-28 rounded-full border-4 flex flex-col items-center justify-center font-mono ${
                      comparisonModal.visual_similarity < 0.85
                        ? 'border-rose-500 bg-rose-950/30 text-rose-300'
                        : 'border-emerald-500 bg-emerald-950/30 text-emerald-300'
                    }`}>
                      <span className="text-3xl font-bold">
                        {comparisonModal.visual_similarity != null ? comparisonModal.visual_similarity.toFixed(2) : '0.00'}
                      </span>
                      <span className="text-[9px] uppercase tracking-wider text-slate-400">512-dim Vector</span>
                    </div>
                  </div>

                  {/* Decision Event */}
                  <div className="w-full">
                    <span className={`block px-2.5 py-1 rounded text-xs font-mono font-bold tracking-wide ${
                      comparisonModal.identity_event === 'POSSIBLE_IDENTITY_MISMATCH'
                        ? 'bg-rose-600 text-white'
                        : comparisonModal.identity_event === 'POSSIBLE_PLATE_SWAP'
                        ? 'bg-purple-600 text-white'
                        : 'bg-emerald-600 text-white'
                    }`}>
                      {comparisonModal.identity_event}
                    </span>
                    <span className="text-[10px] font-mono text-slate-400 block mt-1">
                      {comparisonModal.rule_used}
                    </span>
                  </div>

                  {/* Required Action */}
                  <div className="text-[11px] font-mono text-amber-300 bg-amber-500/10 border border-amber-500/20 rounded p-2 w-full">
                    <strong>Action:</strong> {comparisonModal.action_required}
                  </div>
                </div>

                {/* RIGHT: Historical Baseline Observation */}
                <div className="bg-slate-950 border border-slate-800 rounded-xl p-3 flex flex-col space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-mono text-emerald-400 font-bold uppercase">HISTORICAL PROFILE</span>
                    <span className="text-[10px] font-mono text-slate-500">BASELINE</span>
                  </div>

                  <div className="aspect-video bg-black rounded-lg overflow-hidden border border-slate-800">
                    <img
                      src={getImageUrl(comparisonModal.historical_vehicle_image)}
                      alt="Historical Vehicle"
                      className="w-full h-full object-cover"
                    />
                  </div>

                  {comparisonModal.historical_plate_image && (
                    <div className="h-12 bg-black rounded-lg overflow-hidden border border-slate-800 flex items-center justify-center p-1">
                      <img
                        src={getImageUrl(comparisonModal.historical_plate_image)}
                        alt="Historical Plate"
                        className="max-h-full object-contain"
                      />
                    </div>
                  )}

                  <div className="text-[11px] font-mono text-slate-400 pt-1">
                    Registered Plate: <strong className="text-white">{comparisonModal.historical_plate || 'N/A'}</strong>
                  </div>
                </div>

              </div>
            </div>

            {/* Modal Footer */}
            <div className="px-6 py-3.5 bg-slate-800/80 border-t border-slate-700 flex justify-end space-x-2">
              <button
                onClick={() => setComparisonModal(null)}
                className="px-4 py-2 rounded-lg bg-slate-700 hover:bg-slate-600 text-white font-mono text-xs transition"
              >
                Close Audit
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ==================== MODAL: VEHICLE OBSERVATION HISTORY TIMELINE ==================== */}
      {historyModal && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-700 rounded-2xl max-w-2xl w-full overflow-hidden shadow-2xl">
            <div className="px-6 py-4 bg-slate-800/80 border-b border-slate-700 flex items-center justify-between">
              <h3 className="text-sm font-mono font-bold text-white">
                TIMELINE HISTORY: {historyModal.vehicleId}
              </h3>
              <button
                onClick={() => setHistoryModal(null)}
                className="w-8 h-8 rounded-lg bg-slate-700 hover:bg-slate-600 text-slate-300 flex items-center justify-center font-bold text-lg transition"
              >
                &times;
              </button>
            </div>

            <div className="p-6 max-h-[450px] overflow-y-auto space-y-3">
              {historyModal.records && historyModal.records.length > 0 ? (
                historyModal.records.map((rec, idx) => (
                  <div key={idx} className="p-3 rounded-lg bg-slate-950 border border-slate-800 flex items-center justify-between text-xs font-mono">
                    <div>
                      <div className="text-slate-300 font-bold">{rec.zone} ({rec.camera_id})</div>
                      <div className="text-slate-500 text-[10px] mt-0.5">{rec.timestamp}</div>
                    </div>
                    <div className="text-right">
                      <span className="text-amber-400 font-bold block">{rec.observed_plate || 'NO_PLATE'}</span>
                      <span className="text-[10px] text-slate-400">Sim: {rec.visual_similarity != null ? rec.visual_similarity.toFixed(2) : '1.00'}</span>
                    </div>
                  </div>
                ))
              ) : (
                <div className="text-center text-slate-500 text-xs py-8 font-mono">
                  No observation timeline recorded for this vehicle identity.
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ==================== MODAL: DEMO VEHICLE REGISTRY ==================== */}
      {registryModal && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-700 rounded-2xl max-w-xl w-full overflow-hidden shadow-2xl">
            <div className="px-6 py-4 bg-slate-800/80 border-b border-slate-700 flex items-center justify-between">
              <div>
                <span className="text-[10px] font-mono text-amber-400 font-bold uppercase tracking-wider block">
                  DEMO DATA — NOT LIVE GOVERNMENT RECORD
                </span>
                <h3 className="text-sm font-mono font-bold text-white">
                  VEHICLE REGISTRY LOOKUP ({registryModal.plate})
                </h3>
              </div>
              <button
                onClick={() => setRegistryModal(null)}
                className="w-8 h-8 rounded-lg bg-slate-700 hover:bg-slate-600 text-slate-300 flex items-center justify-center font-bold text-lg transition"
              >
                &times;
              </button>
            </div>

            <div className="p-6 text-xs font-mono space-y-2">
              {registryModal.notFound ? (
                <div className="text-center py-6 text-slate-400">
                  Plate not found in demo registry records.
                </div>
              ) : (
                <div className="space-y-2">
                  <div className="flex justify-between py-1 border-b border-slate-800">
                    <span className="text-slate-400">Plate Number:</span>
                    <span className="font-bold text-white">{registryModal.plate}</span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-slate-800">
                    <span className="text-slate-400">Manufacturer & Model:</span>
                    <span className="text-white">{registryModal.manufacturer} {registryModal.model}</span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-slate-800">
                    <span className="text-slate-400">Registered Colour:</span>
                    <span className="text-white uppercase">{registryModal.colour}</span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-slate-800">
                    <span className="text-slate-400">Vehicle Type:</span>
                    <span className="text-white uppercase">{registryModal.vehicle_type}</span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-slate-800">
                    <span className="text-slate-400">Fuel Type:</span>
                    <span className="text-white uppercase">{registryModal.fuel_type}</span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-slate-800">
                    <span className="text-slate-400">Insurance Status:</span>
                    <span className={registryModal.insurance_status === 'VALID' ? 'text-emerald-400 font-bold' : 'text-rose-400 font-bold'}>
                      {registryModal.insurance_status}
                    </span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-slate-800">
                    <span className="text-slate-400">Fitness Status:</span>
                    <span className={registryModal.fitness_status === 'VALID' ? 'text-emerald-400 font-bold' : 'text-rose-400 font-bold'}>
                      {registryModal.fitness_status}
                    </span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-slate-800">
                    <span className="text-slate-400">PUCC Status:</span>
                    <span className={registryModal.pucc_status === 'VALID' ? 'text-emerald-400 font-bold' : 'text-rose-400 font-bold'}>
                      {registryModal.pucc_status}
                    </span>
                  </div>
                  <div className="flex justify-between py-1">
                    <span className="text-slate-400">Registry Source:</span>
                    <span className="text-amber-400">{registryModal.source}</span>
                  </div>
                </div>
              )}
            </div>

            <div className="px-6 py-3 bg-slate-800/80 border-t border-slate-700 flex justify-end">
              <button
                onClick={() => setRegistryModal(null)}
                className="px-4 py-1.5 rounded bg-slate-700 hover:bg-slate-600 text-white font-mono text-xs transition"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ==================== BACKEND CONFIGURATION MODAL ==================== */}
      {showBackendConfigModal && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-700 rounded-2xl max-w-xl w-full overflow-hidden shadow-2xl">
            <div className="px-6 py-4 bg-slate-800/90 border-b border-slate-700 flex items-center justify-between">
              <div>
                <span className="text-[10px] font-mono uppercase px-1.5 py-0.5 rounded bg-blue-500/20 text-blue-300 border border-blue-500/30">
                  DEPLOYMENT SETTINGS
                </span>
                <h3 className="text-sm font-mono font-bold text-white mt-1">
                  ⚡ FASTAPI BACKEND SERVER CONNECTION
                </h3>
              </div>
              <button
                onClick={() => setShowBackendConfigModal(false)}
                className="w-8 h-8 rounded-lg bg-slate-700 hover:bg-slate-600 text-slate-300 flex items-center justify-center font-bold text-lg transition"
              >
                &times;
              </button>
            </div>

            <div className="p-6 space-y-4 text-xs font-mono">
              <p className="text-slate-300 leading-relaxed">
                Vercel hosts the React Command Center UI. Enter your deployed Render FastAPI backend URL below to connect live telemetry, detection events, and OCR identity matching.
              </p>

              <div className="space-y-2">
                <label className="text-slate-400 text-[11px] block">Current Configured API Base URL:</label>
                <div className="p-2.5 bg-slate-950 border border-slate-800 rounded-lg text-emerald-400 font-mono text-xs break-all">
                  {currentBackendUrl || '(Default Relative / Proxy)'}
                </div>
              </div>

              <div className="space-y-2">
                <label className="text-slate-400 text-[11px] block">Enter Backend Server URL:</label>
                <input
                  type="text"
                  value={customUrlInput}
                  onChange={(e) => setCustomUrlInput(e.target.value)}
                  placeholder="https://visionx-codeavengers-od-08.onrender.com or http://localhost:8000"
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-white font-mono text-xs focus:outline-none focus:border-blue-500"
                />
              </div>

              {/* Preset Quick Buttons */}
              <div className="space-y-1.5">
                <span className="text-slate-500 text-[10px]">QUICK PRESETS:</span>
                <div className="flex flex-wrap gap-2">
                  <button
                    onClick={() => {
                      setCustomUrlInput('https://visionx-codeavengers-od-08.onrender.com');
                      testBackendConnection('https://visionx-codeavengers-od-08.onrender.com');
                    }}
                    className="px-2.5 py-1 rounded bg-blue-900/40 hover:bg-blue-800/60 border border-blue-700 text-blue-200 text-[11px]"
                  >
                    Render Server (https://visionx-codeavengers-od-08.onrender.com)
                  </button>
                  <button
                    onClick={() => {
                      setCustomUrlInput('http://localhost:8000');
                      testBackendConnection('http://localhost:8000');
                    }}
                    className="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 text-[11px]"
                  >
                    Local Host (http://localhost:8000)
                  </button>
                  <button
                    onClick={() => {
                      setCustomUrlInput('');
                      saveBackendUrl('');
                    }}
                    className="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-400 text-[11px]"
                  >
                    Reset to Default
                  </button>
                </div>
              </div>

              {/* Test Result Message */}
              {testResult && (
                <div className={`p-3 rounded-lg border text-xs font-mono ${
                  testResult.success ? 'bg-emerald-950/60 border-emerald-800 text-emerald-300' : 'bg-rose-950/60 border-rose-800 text-rose-300'
                }`}>
                  {testResult.message}
                </div>
              )}

              <div className="pt-2 flex items-center justify-between border-t border-slate-800">
                <button
                  onClick={() => testBackendConnection(customUrlInput)}
                  disabled={isTestingUrl}
                  className="px-3.5 py-1.5 rounded bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200 font-mono text-xs transition disabled:opacity-50"
                >
                  {isTestingUrl ? 'Testing...' : '⚡ Test Connection'}
                </button>

                <div className="flex items-center space-x-2">
                  <button
                    onClick={() => setShowBackendConfigModal(false)}
                    className="px-3.5 py-1.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-400 font-mono text-xs transition"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={() => {
                      saveBackendUrl(customUrlInput);
                      setShowBackendConfigModal(false);
                    }}
                    className="px-4 py-1.5 rounded bg-blue-600 hover:bg-blue-500 text-white font-mono text-xs font-bold transition shadow-lg"
                  >
                    Save & Apply
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ==================== FOOTER ==================== */}
      <footer className="px-6 py-3 bg-slate-900 border-t border-slate-800 text-center text-xs font-mono text-slate-500">
        IVACS V-TRACE &copy; 2026 CodeAvengers | Problem Statement OD-08 | Zero LLM Native CV Architecture
      </footer>
    </div>
  );
}
