/* CodeDeck's page: the page every project tool draws (kit/ProjectApp.jsx). kit/ is copied from tools/webkit by build.mjs. */
import { createRoot } from 'react-dom/client';
import { startMode } from './kit/bridge.js';
import { ProjectApp } from './kit/ProjectApp.jsx';
import './kit/kit.css';

startMode();
createRoot(document.getElementById('root')).render(<ProjectApp />);
