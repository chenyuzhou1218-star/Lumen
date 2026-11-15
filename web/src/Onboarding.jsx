import { useEffect, useRef, useState } from 'react';
import { Combo, Segmented, Select, Switch } from './Controls.jsx';
import { Icon } from './icons.jsx';

/* Before any window: the greeting, written stroke by stroke in ten languages; the first-run setup (the language,
   then the AIs); and the one card for a folder that could not be opened. The words are the ones the Qt cards used, in
   the ten interface languages, sent by Python (desktop/web_onboarding.py), which also builds and saves the setup. */

const GREETINGS = [['Hello', 'Segoe Script'], ['Bonjour', 'Segoe Script'], ['你好', 'KaiTi'], ['Hola', 'Segoe Script'], ['Olá', 'Segoe Script'],
  ['こんにちは', 'MS Gothic'], ['Привет', 'Segoe Script'], ['Hallo', 'Segoe Script'], ['Ciao', 'Segoe Script'], ['안녕하세요', 'Malgun Gothic']];
const CYCLE = 1800;

/* One greeting after another: its outline traced, then filled from left to right, then gone. Done after all ten. */
export function Greeting({ onDone, still }) {
  const [i, setI] = useState(0);
  const text = useRef(null);
  useEffect(() => {
    if (still) return undefined;
    let frame = 0;
    const start = performance.now();
    const step = (now) => {
      const time = Math.max(0, now - start); // the first frame can be stamped before the start
      if (time >= GREETINGS.length * CYCLE) { onDone && onDone(); return; }
      const idx = Math.floor(time / CYCLE);
      const phase = (time % CYCLE) / CYCLE;
      const raw = phase < 0.77 ? Math.min(1, phase / 0.54) : Math.max(0, 1 - (phase - 0.77) / 0.23);
      const p = raw * raw * (3 - 2 * raw);
      setI(idx);
      const el = text.current;
      if (el) {
        el.style.strokeDashoffset = String(2400 * (1 - p));
        el.style.fillOpacity = String(Math.min(1, p * 1.3));
        el.style.opacity = phase < 0.77 ? '1' : String(raw);
      }
      frame = requestAnimationFrame(step);
    };
    frame = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frame);
  }, [still]); // eslint-disable-line react-hooks/exhaustive-deps
  const [word, family] = still ? GREETINGS[0] : GREETINGS[i];
  return (
    <svg className="greeting" viewBox="0 0 800 200" role="img" aria-label={word}>
      <text ref={text} x="400" y="128" textAnchor="middle" fontFamily={family} fontSize="104" className="greeting-word"
        style={still ? { strokeDashoffset: 0, fillOpacity: 1 } : undefined}>{word}</text>
    </svg>
  );
}

export function Welcome({ texts, proceed, still }) {
  const gone = useRef(false);
  const go = () => { if (!gone.current) { gone.current = true; proceed(); } };
  return (
    <div className="ob-card welcome">
      <header className="ob-top"><span className="ob-mark" /><b>Lumen</b><span className="grow" /><small>SOFTWARE · SYSTEMS · LOGIC</small></header>
      <Greeting onDone={go} still={still} />
      <p className="ob-tagline">{texts.tagline}</p>
      <footer className="ob-foot"><span className="grow" />
        <button className="btn ghost" onClick={go}>{texts.skip}</button>
        <button className="btn primary" onClick={go}>{texts.enter}</button>
      </footer>
    </div>
  );
}

function Setup({ api }) {
  const [s, setS] = useState(null);
  const [step, setStep] = useState(0);
  const [chosen, setChosen] = useState([]);
  const [preset, setPreset] = useState('');
  const [url, setUrl] = useState('');
  const [key, setKey] = useState('');
  const [model, setModel] = useState('');
  const [models, setModels] = useState([]);
  const [fix, setFix] = useState(true);
  const [tested, setTested] = useState(null);
  const [error, setError] = useState('');
  const load = async () => {
    const r = await api.obSetup();
    setS(r);
    const p = r.presets[0];
    setPreset((x) => x || p.id);
    setUrl((x) => x || p.base_url);
    api.obCheck();
  };
  useEffect(() => { load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    const offShow = api.on('show', (v) => { if (v.relanguage) load(); });
    const offStatus = api.on('status', (st) => {
      setS((x) => x && { ...x, engines: x.engines.map((e) => (e.name === st.name ? { ...e, status: st.status, text: st.text } : e)) });
      if (st.status === 'ready') setChosen((c) => (c.length ? c : [st.name])); // a ready one is the natural first choice
    });
    const offTested = api.on('tested', (r) => { setTested(r); if (r.models && r.models.length) setModels(r.models); });
    return () => { offShow(); offStatus(); offTested(); };
  }, [api]); // eslint-disable-line react-hooks/exhaustive-deps
  if (!s) return <div className="ob-card"><span className="spin" /></div>;
  const tx = s.texts;
  const p = s.presets.find((x) => x.id === preset) || s.presets[0];
  const toggle = (name) => setChosen((c) => (c.includes(name) ? c.filter((x) => x !== name) : [...c, name]));
  const pickPreset = (id) => {
    const q = s.presets.find((x) => x.id === id);
    setPreset(id); setUrl(q.base_url); setModel(''); setModels([]); setTested(null);
  };
  const finish = async () => {
    setError('');
    const r = await api.obFinish({ chosen, preset, url, key, model, fix });
    if (!r.ok) setError(r.error);
  };
  const first = chosen[0];
  const firstName = first ? (s.engines.find((e) => e.name === first) || {}).title || p.name : '';
  return (
    <div className="ob-card setup">
      <header className="ob-top"><span className="ob-mark" /><b>Lumen</b><span className="grow" /><small>{step + 1} / 2</small></header>
      {step === 0 ? (
        <div className="ob-body" key="place">
          <h1>{tx.lang_title}</h1>
          <div className="ob-langs">
            {s.langs.map((l) => (
              <button key={l.value} className={`ob-choice${l.value === s.lang ? ' on' : ''}`} onClick={() => l.value !== s.lang && api.obLanguage(l.value)}>
                {l.label}{l.value === s.lang && <Icon name="check" size={15} />}
              </button>
            ))}
          </div>
        </div>
      ) : (
        <div className="ob-body" key="ai">
          <h1>{tx.pick_ai_title}</h1>
          <p className="ob-sub">{tx.pick_ai_sub}</p>
          {s.engines.map((e) => (
            <label key={e.name} className={`ob-ai${chosen.includes(e.name) ? ' on' : ''}${e.status === 'missing' ? ' off' : ''}`}>
              <input type="checkbox" checked={chosen.includes(e.name)} disabled={e.status === 'missing'} onChange={() => toggle(e.name)} />
              <span className="two"><b>{e.title}</b><small>{tx[`use_${e.name}_sub`]}</small>
                <em className={e.status === 'ready' ? 'good' : ''}>{e.status ? '' : <span className="spin" />}{e.text}</em></span>
            </label>
          ))}
          <label className={`ob-ai${chosen.includes('api') ? ' on' : ''}`}>
            <input type="checkbox" checked={chosen.includes('api')} onChange={() => toggle('api')} />
            <span className="two"><b>{tx.use_api}</b><small>{tx.use_api_sub}</small></span>
          </label>
          {chosen.includes('api') && (
            <div className="ob-api">
              <div className="ob-row"><span>{tx.service}</span><Select value={preset} options={s.presets.map((x) => ({ value: x.id, label: x.name }))} onChange={pickPreset} /></div>
              <div className="ob-row"><span>{tx.address}</span><input className="input mono" value={url} onChange={(e) => setUrl(e.target.value)} /></div>
              {!p.local && (
                <div className="ob-row"><span>{tx.api_key}</span><div className="ob-col">
                  <input className="input mono" type="password" autoComplete="off" value={key} onChange={(e) => setKey(e.target.value)} />
                  <small className="hint">{tx.key_hint}</small></div></div>
              )}
              {p.local && <p className="hint">{tx.no_key_needed}</p>}
              <div className="ob-row"><span>{tx.model}</span><div className="ob-col">
                <div className="test-row"><Combo value={model} options={models} onCommit={setModel} placeholder={tx.model_hint} />
                  <button className="btn small" onClick={() => { setTested({ busy: true, text: tx.testing }); api.obTest({ preset, url, key, model }); }}>{tx.test}</button></div>
                {tested && <p className={`result ${tested.busy ? 'busy' : tested.ok ? 'good' : 'bad'}`}>{tested.busy && <span className="spin" />}<span>{tested.text}</span></p>}
              </div></div>
            </div>
          )}
          <Switch on={fix} label={tx.let_fix} note={tx.let_fix_sub} onChange={setFix} />
          {firstName && <p className="ob-default"><Icon name="check" size={14} />{(tx.default_ai || '{0}').replace('{0}', firstName)}</p>}
        </div>
      )}
      {error && <p className="result bad"><Icon name="warn" size={14} /><span>{error}</span></p>}
      <footer className="ob-foot">
        {step > 0 && <button className="btn ghost" onClick={() => setStep(0)}>{tx.back}</button>}
        <span className="grow" />
        {step === 0 ? <button className="btn primary" onClick={() => setStep(1)}>{tx.next}</button>
          : <button className="btn primary" onClick={finish}>{tx.start_using}</button>}
      </footer>
    </div>
  );
}

function Failed({ api, view, texts }) {
  return (
    <div className="ob-card failed">
      <span className="ob-mark big" />
      <h2>{view.title}</h2>
      <p className="result bad"><span>{view.why}</span></p>
      <button className="btn primary" onClick={() => api.obChoose()}><Icon name="folder" size={15} />{texts.open_folder}</button>
    </div>
  );
}

export function Onboarding({ api, texts, still }) {
  const [view, setView] = useState(null);
  useEffect(() => {
    api.obCurrent().then(setView);
    return api.on('show', (v) => { if (['welcome', 'setup', 'failed'].includes(v.page) && !v.relanguage) setView(v); });
  }, [api]);
  if (!view) return <div className="onboarding" />;
  return (
    <div className="onboarding">
      {view.page === 'welcome' && <Welcome texts={texts} proceed={() => api.obProceed()} still={still} />}
      {view.page === 'setup' && <Setup api={api} />}
      {view.page === 'failed' && <Failed api={api} view={view} texts={texts} />}
    </div>
  );
}
