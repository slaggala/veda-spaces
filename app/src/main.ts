import './design-system/tokens.css';
import './design-system/components.js';
import './core/authz/can.js';
import { installGlobalHandlers } from './core/telemetry/telemetry.js';
import './shell/app.js';

installGlobalHandlers();
